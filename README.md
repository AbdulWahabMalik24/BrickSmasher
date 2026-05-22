# BrickSmasher
A full-stack Flask + SQLite VHS rental system with real-time updates using AJAX (fetch()).

## Overview
BrickSmasher simulates a video rental store where users can manage members, movies, and rentals through a responsive web interface with live updates and no page reloads.

## Key Features
  - Member account system with email validation
  - Movie inventory management (add/remove stock)
  - Real-time availability tracking
  - Rental and return system with business rules:
    - Unique users and titles
    - Max 3 active rentals per user
    - No duplicate or unavailable rentals
  - Fully AJAX-driven UI (no page refreshes)

## Tech Stack
  - Backend: Flask (Python)
  - Database: SQLite
  - Frontend: HTML, CSS, Vanilla JavaScript
  - Async: Fetch API (AJAX)

## Project Structure
BrickSmasher/
├── app.py
├── schema.sql
├── database.db
├── templates/
│   ├── home.html
│   ├── account.html
│   ├── movie.html
│   └── rent.html
├── static/
│   ├── style.css
│   └── app.js
└── README.md

## Setup
1. Install Flask:
  pip install flask

2. Run the app:
  python app.py

3. Open:
  http://127.0.0.1:5000/

## API Design
  - /dbUser/ → create & fetch users
  - /dbMovie/ → manage inventory
  - /dbRent/ → handle rentals & returns

## Technical Highlights
  - Full-stack CRUD application design
  - REST-style API structure
  - Client-side state updates with AJAX
  - Database-driven business logic enforcement