# Café Analytics

A restaurant and café management system with a built-in analytics dashboard. Customers scan a QR code at their table to browse the menu and order from their phone, while staff and the kitchen manage everything from one place. The dashboard turns order and review data into insights for the owner.

## Features

**Customer side**
- Scan the table QR code to see the full menu with details for every dish
- Place orders directly from the phone
- View the bill, split it, add a tip and pay at the table
- Get the receipt by email and leave a review with one tap

**Staff and kitchen side**
- Orders reach the kitchen in one tap
- Kitchen display with live orders and timers
- Call a waiter to the table with one tap

**Analytics dashboard** (Streamlit)
- Revenue, total orders and average order value
- Best-selling dishes
- Orders by hour (peak times)
- Daily revenue trend
- Average order value by weekday
- Customer ratings and review overview
- Date range filter

## Tech Stack

- Python
- Streamlit (dashboard UI)
- Pandas (data handling)
- Plotly (charts)
- SQLite (database)

## Project Structure

```bash
pip install -r requirements.txt
python seed.py                       # menu + synthetic orders
uvicorn main:app --reload --host 0.0.0.0
python make_qr.py http://<your-LAN-IP>:8000 12
streamlit run dashboard.py
```
Open `http://localhost:8000/t/5` on a phone and `http://localhost:8000/kitchen` on a laptop.


`cafe.db` is created locally and is not committed to the repository.

## Database Schema

| Table | Columns |
|---|---|
| `orders` | `id`, `table_no`, `created_at` |
| `order_items` | `order_id`, `name`, `qty`, `price` |
| `reviews` | `rating`, `comment` |

## Getting Started

1. Clone the repository
   ```bash
   git clone https://github.com/<your-username>/<repo-name>.git
   cd <repo-name>
   ```

2. Create a virtual environment and install dependencies
   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Generate sample data
   ```bash
   python seed.py
   ```

4. Run the dashboard
   ```bash
   streamlit run app.py
   ```

   The app opens at `http://localhost:8501`.

## Roadmap (Machine Learning)

ML features planned on top of the existing order and review data:

- [ ] Demand forecasting (orders and dish-level sales)
- [ ] Dish recommendations using market basket analysis
- [ ] Review sentiment analysis and common complaint detection
- [ ] Order wait-time prediction for the kitchen display
- [ ] Peak hour prediction for staff scheduling

## Contributing

Suggestions and pull requests are welcome. Please open an issue first to discuss major changes.
