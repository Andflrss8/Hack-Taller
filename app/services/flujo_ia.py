"""
services/flujo_ia.py

Orquesta el flujo compartido entre los routers (ESP32, Predicciones y Ofertas):
- Prepara los datos reales de BD (lecturas, categoría, ubicación del negocio).
- Invoca a Gemini con el prompt de seguridad.
- Guarda Prediccion, PrediccionLectura y Oferta en MySQL.
- Busca receptores registrados en la BD ordenados por distancia.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
import os
from typing import List, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    CategoriaAlimento,
    EstadoOferta,
    LecturaPeso,
    Oferta,
    Prediccion,
    PrediccionLectura,
    RolUsuario,
    Usuario,
    utcnow,
)
from app.schemas import (
    AnalisisCompletoIAResponse,
    CentroDonacionPublic,
    OfertaPublic,
    ReceptorCercano,
)
from app.services.gemini_service import (
    GEMINI_MODEL,
    analizar_lecturas_con_gemini,
    calcular_distancia_km,
    resultado_ia_fallback,
)


def construir_info_negocio(usuario: Usuario) -> dict:
    """Extrae la información relevante de ubicación y giro del negocio."""
    return {
        "nombre_negocio": usuario.nombre_negocio or usuario.nombre,
        "tipo_negocio": usuario.tipo_negocio.value if usuario.tipo_negocio else "NO_ESPECIFICADO",
        "direccion": usuario.direccion,
        "ciudad_region": usuario.ciudad_region,
        "estado": usuario.estado,
        "pais": usuario.pais or "México",
        "latitud": float(usuario.latitud) if usuario.latitud is not None else None,
        "longitud": float(usuario.longitud) if usuario.longitud is not None else None,
    }


def obtener_receptores_cercanos(session: Session, vendedor: Usuario) -> List[ReceptorCercano]:
    """
    Busca usuarios con rol RECEPTOR en la base de datos y calcula su distancia
    aproximada al local del vendedor si ambos tienen coordenadas.
    """
    receptores = session.exec(
        select(Usuario).where(Usuario.rol == RolUsuario.RECEPTOR)
    ).all()

    resultados: List[ReceptorCercano] = []
    for rec in receptores:
        distancia = None
        if (
            vendedor.latitud is not None
            and vendedor.longitud is not None
            and rec.latitud is not None
            and rec.longitud is not None
        ):
            distancia = calcular_distancia_km(
                float(vendedor.latitud),
                float(vendedor.longitud),
                float(rec.latitud),
                float(rec.longitud),
            )

        resultados.append(
            ReceptorCercano(
                id=rec.id,
                nombre=rec.nombre,
                nombre_negocio=rec.nombre_negocio,
                telefono=rec.telefono,
                direccion=rec.direccion,
                ciudad_region=rec.ciudad_region,
                distancia_km=distancia,
            )
        )

    # Ordenar primero los que tienen distancia calculada (de menor a mayor)
    resultados.sort(key=lambda r: (r.distancia_km is None, r.distancia_km or 0.0))
    return resultados


def ejecutar_analisis_y_guardar(
    session: Session,
    vendedor: Usuario,
    categoria: CategoriaAlimento,
    lecturas: List[LecturaPeso],
    fecha_objetivo: Optional[date] = None,
    crear_oferta: bool = True,
) -> AnalisisCompletoIAResponse:
    """
    Ejecuta el análisis con Gemini sobre lecturas reales, valida con el prompt
    de seguridad y guarda la Prediccion (y opcionalmente la Oferta) en MySQL.
    """
    if not lecturas:
        raise HTTPException(
            status_code=400,
            detail="Se requiere al menos una lectura de peso para generar una predicción.",
        )

    lecturas_info = [
        {
            "id": l.id,
            "peso_g": float(l.peso_g),
            "descripcion": l.descripcion,
            "tipo": l.tipo.value,
            "fecha_hora": l.fecha_hora.isoformat(),
            "es_simulada": l.es_simulada,
        }
        for l in lecturas
    ]

    categoria_info = {
        "id": categoria.id,
        "nombre": categoria.nombre,
        "es_perecedero": categoria.es_perecedero,
        "vida_util_dias": categoria.vida_util_dias,
    }

    negocio_info = construir_info_negocio(vendedor)

    try:
        resultado_ia = analizar_lecturas_con_gemini(
            lecturas_info=lecturas_info,
            categoria_info=categoria_info,
            negocio_info=negocio_info,
        )
    except Exception:
        # Sin clave real o fallo de Gemini: la demo continúa con datos de ejemplo.
        resultado_ia = resultado_ia_fallback(
            lecturas_info=lecturas_info,
            categoria_info=categoria_info,
            negocio_info=negocio_info,
        )

    # Regla de seguridad: si el prompt detecta datos ajenos o inválidos, rechaza
    if not resultado_ia.valido or not resultado_ia.prediccion:
        raise HTTPException(
            status_code=400,
            detail=f"Datos rechazados por validación de seguridad IA: {resultado_ia.motivo_rechazo or 'Contenido fuera de propósito.'}",
        )

    # 1. Guardar la Predicción en MySQL
    prediccion = Prediccion(
        usuario_id=vendedor.id,
        categoria_id=categoria.id,
        fecha_objetivo=fecha_objetivo or date.today(),
        kg_estimados=Decimal(str(round(resultado_ia.prediccion.kg_estimados, 2))),
        confianza=Decimal(str(round(resultado_ia.prediccion.confianza, 4))),
        modelo=os.getenv("GEMINI_MODEL", GEMINI_MODEL),
        creada_en=utcnow(),
    )
    session.add(prediccion)
    session.commit()
    session.refresh(prediccion)

    # 2. Vincular las lecturas en PREDICCION_LECTURAS (tabla N:M)
    for l in lecturas:
        session.add(PrediccionLectura(prediccion_id=prediccion.id, lectura_id=l.id))
    session.commit()

    # 3. Guardar la Oferta sugerida si aplica
    oferta_publica: Optional[OfertaPublic] = None
    if crear_oferta and resultado_ia.oferta_sugerida:
        ahora = utcnow()
        horas = max(1, min(resultado_ia.oferta_sugerida.horas_ventana_sugeridas, 72))
        oferta_creada = Oferta(
            usuario_id=vendedor.id,
            prediccion_id=prediccion.id,
            categoria_id=categoria.id,
            titulo=resultado_ia.oferta_sugerida.titulo[:255],
            descripcion=resultado_ia.oferta_sugerida.descripcion[:255],
            kg_disponibles=Decimal(str(round(resultado_ia.oferta_sugerida.kg_disponibles, 2))),
            ventana_inicio=ahora,
            ventana_fin=ahora + timedelta(hours=horas),
            estado=EstadoOferta.ACTIVA,
        )
        session.add(oferta_creada)
        session.commit()
        session.refresh(oferta_creada)
        # Se convierte a esquema público: el modelo ORM trae la relación `categoria`
        # como objeto, pero el panel espera el nombre como texto.
        oferta_publica = OfertaPublic.model_validate(
            {
                **oferta_creada.model_dump(),
                "categoria": categoria.nombre,
                "cantidad_kg": oferta_creada.kg_disponibles,
            }
        )

    # 4. Obtener receptores registrados + centros sugeridos por Gemini
    receptores = obtener_receptores_cercanos(session, vendedor)
    centros = [
        CentroDonacionPublic(**c.model_dump())
        for c in resultado_ia.centros_donacion_cercanos
    ]

    return AnalisisCompletoIAResponse(
        lectura=lecturas[0] if len(lecturas) == 1 else None,
        prediccion=prediccion,
        oferta=oferta_publica,
        justificacion_ia=resultado_ia.prediccion.justificacion,
        receptores_registrados=receptores,
        centros_donacion_sugeridos=centros,
    )
