# Perfume Fit AI Recommender

## What is this?

I made a quiz that helps people find perfumes they'll like on my store (perfume.fit). It asks a few questions and then suggests actual products from my shop.

## Try it out

- **Live demo:** https://perfumefit.onrender.com
- **My store:** https://perfume.fit

## How it works

1. You answer questions like:
   - Are you shopping for yourself or as a gift?
   - What's your favorite color?
   - What kind of scents do you like? (floral, woody, citrus, etc.)

2. The AI looks through my real Shopify products

3. It shows you perfumes that match your answers with pictures and prices

## What I used to build this

- Django (Python web framework)
- Shopify API (to get real product data)
- HTML/CSS/JavaScript (for the quiz look and feel)
- Render (to put it online)

## How to run it on your computer

1. Clone this repo
2. Install stuff: `pip install -r requirements.txt`
3. Run it: `python manage.py runserver`
4. Go to `http://127.0.0.1:8000` in your browser

## The cool features

- Saves your answers if you accidentally refresh
- Works on phones and computers
- Has a little help button if you get stuck
- Shows real products from my actual store (not fake examples)

## What I learned

- How to connect a Django app to Shopify
- How to deploy something online so anyone can use it
- Making a quiz that changes questions based on your answers

## Links

- My perfume store: https://perfume.fit
- Live AI demo: https://perfumefit.onrender.com

---

Made by me for perfume.fit ✨
