# NovaMart Public Dataset

The supplied public dataset is stored in `data/public/`.

- `customers.csv` — 1,500 customers
- `products.csv` — 300 products
- `orders.csv` — 8,000 orders
- `order_items.csv` — 12,444 order items
- `support_tickets.csv` — 2,500 tickets
- `reviews.csv` — 3,000 reviews
- `conversations.json` — 1,500 conversation records
- `policies/*.md` — versioned and supporting policy documents
- `products/*.md` — product-category specification documents

`app/db.py` loads these files into SQLite at startup. `app/tools.py` uses the real dataset column names, while `app/policy.py` selects Refund Policy v1/v2 from the order placement date.
