# firelens
A REST API with the intent of developing a user-friendly interface for obtaining information on fire department incidents around the city of Seattle.

API is a major work in progress, and I admittedly have very little experience with this kind of thing. Firelens is another learning project to familiarize myself with Python (and by extension, building APIs) so please keep that in mind if you intend to use this. And of course, by all means contribute/give feedback if you'd like!


![](https://i.imgur.com/g4ci3nF.png)

# Usage

First, install the required dependencies.
```
pip install -Ur requirements.txt
```

Once installed, run the server with:
```md
uvicorn api:app --reload

# OR

py api.py
```

The output log will provide you with the URL to your service (often http://127.0.0.1:8000). Navigate to http://127.0.0.1:8000/docs to view the documentation on the API and test it out.

# Disclaimer

I, nor this repository, have any official association with the Seattle Fire Department or any government entity.
