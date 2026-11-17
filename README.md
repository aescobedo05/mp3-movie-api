# MP3 Persistent Storage and Caching
This application extends upon `mp2-rest-api`, an API I created, by adding SQLite database to store, retrive, filter, and update movie records. It also uses fakeredis to practice caching repeated requests. `data_pipeline/` contains an earlier created pipeline of mine, which I explain in `mp1-data-pipeline`. `fixture/` contain the messy data file used to test my application. `test/` contains `conftests.py` and `test_api.py` which is where the set up and actual test files live. Finally `src/` contains the `database.py`, `middleware.py`, `models.py`, `storage.py`, `cache.py`, and `utils.py`. 

`database.py` helps set up a connection to the database and creates a new movie table if one doesn't already exist. `utils.py` sets up the logger and checks for valid file inputs and `models.py` defines all the BaseModels used. `storage.py` creates the MovieStorage class which contains the basic query functions like adding a new dataset to the table, returning the existing data in the table or counting the number of stored movies, for example. `middleware.py` makes it so each endpoint in the API has a logger message and HTTP status code and last but not least `cache.py` helps with practice caching.
#
### Command to start API
`python -m uvicorn main:app --reload`

### Interactive documentation page
`http://127.0.0.1:8000/docs`

### Command to run test
`python -m pytest tests -v`

## Sample processing request 
### Input
```json
{
  "validation": {
    "required_columns": [
      "title", "release_year", "rating", "genre"
    ],
    "numeric_columns": [
      "release_year", "rating"
    ]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {
      "enabled": true,
      "axis": "rows"
    },
    "outliers": {
      "enabled": true,
      "columns": [
        "string"
      ],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```
### Result
```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```
