import io
import json
import logging
from pathlib import Path
import pandas as pd

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import HealthResponse, setup_logging, ProcessConfig, log_requests, MovieStorage, MovieUploadInfo, MovieDataResponse, MovieProcessingReport, MOVIE_COLUMNS, MovieCache
from data_pipeline import create_cleaning_report, process_data, validate_dataframe


cache = MovieCache()

storage = MovieStorage()

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")

app.middleware("http")(log_requests)

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": "1.0.0"}

@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read and store a CSV upload."""
    contents = await file.read()

    data_dir = Path(file.filename or "").suffix.lower()
    if data_dir != '.csv':
        logger.warning("Extension not .csv")
        raise HTTPException(status_code=400, detail="Extension not .csv")

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (pd.errors.EmptyDataError,pd.errors.ParserError,UnicodeDecodeError) as error:
        logger.warning("Cannot read CSV: %s", error)
        raise HTTPException(status_code=400, detail="Cannot read the uploaded CSV") from error

    if set(df.columns) != set(MOVIE_COLUMNS):
        missing_columns = (set(MOVIE_COLUMNS) - set(df.columns))
        raise HTTPException(status_code=400, detail=f"need {missing_columns} column")

    if df.empty:
        raise HTTPException(status_code=400, detail="empty dataframe")

    df = df[MOVIE_COLUMNS]

    cache.invalidate()
    storage.save(df)
    
    logger.info("Uploaded movies: filename=%s, rows= %s", file.filename, len(df))

    return MovieUploadInfo(
        filename=file.filename or "",
        rows=len(df),
        columns=len(df.columns),
        column_names=df.columns.tolist(),
    )

@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return up to limit movies and the total movie count."""
    cached = cache.get(limit)
    if cached is not None:
        logger.info("movie rows=%s", len(cached["data"]))
        return cached

    records = storage.select_columns(MOVIE_COLUMNS, limit)
    total_rows = storage.count_movies()
    response = {"data": records, "total_rows": total_rows}

    cache.set(limit, response)

    logger.info("Retrieved movies: returned_rows=%s, total_rows=%s", len(records), total_rows)

    return response

@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1)
):
    try:
        records = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    logger.info("Queried movies: columns=%s, min_rating=%s, returned_rows=%s", columns, min_rating, len(records))

    return records


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    """Validate and process a stored dataset using MP1 functions."""
    try:
        dataset = storage.get()
    except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    settings = config.model_dump()

    req_columns = settings["validation"]["required_columns"]
    num_columns = settings["validation"]["numeric_columns"]

    for column in num_columns:
        if column not in dataset.columns:
            logger.warning("Dataset missing numeric column: %s", column)
            raise HTTPException(status_code=400, detail=f"Missing numeric column: {column}")

    try:
        validated_df = validate_dataframe(dataset.copy(), req_columns, num_columns)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    df = validated_df.copy()
    validation_rows_removed =(len(dataset) - len(validated_df))

    try:
        processed_df = process_data(df, settings)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    report = create_cleaning_report(validated_df, processed_df)
    storage.save(processed_df)
    cache.invalidate() 

    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": report
    }
