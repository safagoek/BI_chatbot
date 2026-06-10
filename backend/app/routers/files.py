"""
app/routers/files.py
Dosya yükleme ve yönetim endpoint'leri.
"""
import os
import re
import uuid
import shutil
import pandas as pd
from typing import Any, Dict, List
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.database.manager import (
    add_uploaded_file, get_uploaded_files, get_file_by_id, delete_uploaded_file,
)
from app.core.logger import logger
from app.core.config import settings

router = APIRouter(prefix="/api/files", tags=["files"])

UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), settings.upload_dir)
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("")
def list_files():
    try:
        return get_uploaded_files()
    except Exception as e:
        logger.error(f"list_files error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}/preview")
def get_file_preview(file_id: str):
    try:
        file_meta = get_file_by_id(file_id)
        if not file_meta:
            raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")

        save_path = file_meta["file_path"]
        suffix = os.path.splitext(save_path)[1].lower()

        if not os.path.exists(save_path):
            raise HTTPException(status_code=404, detail="FILE_MISSING_ON_DISK")

        if suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(save_path)
        else:
            sep = "\t" if suffix == ".tsv" else ","
            df = pd.read_csv(save_path, sep=sep)

        df_preview = df.head(20).fillna("")
        preview_data = {
            "columns": list(df_preview.columns),
            "rows": df_preview.values.tolist(),
            "row_count": len(df),
            "alias": file_meta["alias"],
            "id": file_meta["id"],
            "schema": file_meta["schema"],
        }
        return {"success": True, "preview": preview_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PREVIEW_FAILED: {str(e)}")


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    alias: str = Form(...),
):
    filename = file.filename
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in [".csv", ".tsv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_FILE_FORMAT")

    clean_alias = re.sub(r"[^a-zA-Z0-9_]", "", alias.strip().replace(" ", "_"))
    if not clean_alias:
        clean_alias = f"file_{uuid.uuid4().hex[:6]}"

    file_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOAD_DIR, f"{file_id}{suffix}")

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FILE_WRITE_FAILED: {str(e)}")

    try:
        if suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(save_path)
        else:
            sep = "\t" if suffix == ".tsv" else ","
            df = pd.read_csv(save_path, sep=sep)

        row_count = len(df)
        schema: Dict[str, str] = {}
        for col in df.columns:
            dtype = str(df[col].dtype)
            if "int" in dtype or "float" in dtype:
                schema[col] = "Sayı"
            elif "bool" in dtype:
                schema[col] = "Boole"
            elif "datetime" in dtype or "date" in dtype:
                schema[col] = "Tarih"
            else:
                schema[col] = "Metin"

        file_meta = add_uploaded_file(
            file_id=file_id,
            alias=clean_alias,
            original_name=filename,
            file_path=save_path,
            row_count=row_count,
            schema=schema,
        )

        df_preview = df.head(20).fillna("")
        preview_data = {
            "columns": list(df_preview.columns),
            "rows": df_preview.values.tolist(),
            "row_count": row_count,
        }

        return {"success": True, "metadata": file_meta, "preview": preview_data}

    except ValueError as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=422, detail=f"FILE_PARSE_FAILED: {str(e)}")


@router.delete("/{file_id}")
def delete_file(file_id: str):
    success = delete_uploaded_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
    return {"success": True, "message": "Dosya başarıyla silindi."}
