import os

class Config:
    SQLALCHEMY_DATABASE_URI = (
        'mssql+pyodbc://DESKTOP-5E21SBF\\SQLEXPRESS/bmdb'
        '?driver=ODBC+Driver+17+for+SQL+Server'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False# Configuration settings 
