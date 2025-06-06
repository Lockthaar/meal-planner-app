import streamlit as st
import sqlite3
import pandas as pd
import hashlib

# -------------------------------------------------------------------
# CONFIGURATION DE L'APPLICATION
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Batchist",
    page_icon="🍲",
    layout="wide",
)

# -------------------------------------------------------------------
# INITIALISATION DE LA BASE DE DONNÉES (SQLite)
# -------------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    """
    Retourne une connexion thread-safe à la base SQLite.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    """
    Crée les tables si elles n'existent pas encore :
      - users
      - recipes
      - mealplans (sans colonne timestamp pour éviter toute erreur)
    """
    conn = get_connection()
    cursor = conn.cursor()
    # Table des utilisateurs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    """)
    # Table des recettes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            instructions TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    # Table des plans de repas (sans timestamp)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mealplans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            meal TEXT NOT NULL,
            recipe_name TEXT NOT NULL,
            FOREIGN KEY
