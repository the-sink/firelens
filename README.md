# firelens
A REST API with the intent of developing a user-friendly interface for obtaining information on fire department incidents around the city of Seattle.

# Usage

First, install the required dependencies.
```
pip install -Ur requirements.txt
```

Once installed, run the server with:
```
uvicorn api:app --reload
```

The output log will provide you with the URL to your service (often http://127.0.0.1:8000). Navigate to http://127.0.0.1:8000/docs to view the documentation on the API and test it out.