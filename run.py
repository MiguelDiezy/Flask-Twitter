from distutils.log import debug
from flask import Flask
from app.main import app

if __name__ == "__main__":
    app.run(debug=True)