import os, sqlite3, subprocess, sys

def has_data():
    if not os.path.exists("cafe.db"):
        return False
    c = sqlite3.connect("cafe.db")
    try:
        return c.execute("SELECT COUNT(*) FROM orders").fetchone()[0] > 0
    except sqlite3.OperationalError:
        return False
    finally:
        c.close()

if not has_data():
    subprocess.run([sys.executable, "seed.py"], check=True)
import sqlite3, pandas as pd, plotly.express as px, streamlit as st
st.set_page_config(page_title="Café Analytics", layout="wide")
st.title("Café analytics")
con = sqlite3.connect("cafe.db")
df = pd.read_sql("""SELECT o.id order_id, o.table_no, o.created_at, i.name, i.qty, i.price, i.qty*i.price AS amount
                    FROM orders o JOIN order_items i ON i.order_id=o.id""", con, parse_dates=["created_at"])
if df.empty: st.warning("No data yet. Run `python seed.py`."); st.stop()
df["hour"] = df.created_at.dt.hour; df["day"] = df.created_at.dt.date; df["weekday"] = df.created_at.dt.day_name()
dmin, dmax = df.day.min(), df.day.max()
lo, hi = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax) if True else (dmin, dmax)
df = df[(df.day >= lo) & (df.day <= hi)]
orders = df.groupby("order_id").amount.sum()
a, b, c = st.columns(3)
a.metric("Revenue", f"₹{df.amount.sum():,.0f}"); b.metric("Orders", f"{len(orders):,}"); c.metric("Average order value", f"₹{orders.mean():,.0f}")
l, r = st.columns(2)
top = df.groupby("name").qty.sum().nlargest(8).reset_index()
l.plotly_chart(px.bar(top, x="qty", y="name", orientation="h", title="Best-selling dishes").update_yaxes(autorange="reversed"), use_container_width=True)
byh = df.groupby("hour").order_id.nunique().reset_index(name="orders")
r.plotly_chart(px.bar(byh, x="hour", y="orders", title="Orders by hour (peak times)"), use_container_width=True)
rev = df.groupby("day").amount.sum().reset_index()
st.plotly_chart(px.line(rev, x="day", y="amount", title="Daily revenue"), use_container_width=True)
order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
wd = df.groupby(["weekday","order_id"]).amount.sum().reset_index().groupby("weekday").amount.mean().reindex(order).reset_index()
st.plotly_chart(px.bar(wd, x="weekday", y="amount", title="Average order value by weekday"), use_container_width=True)

rv = pd.read_sql("SELECT rating, comment FROM reviews", con)
if not rv.empty:
    st.subheader("Customer reviews")
    x, y = st.columns(2)
    x.metric("Average rating", f"{rv.rating.mean():.2f} / 5")
    y.plotly_chart(px.bar(rv.rating.value_counts().sort_index().reset_index(), x="rating", y="count", title="Ratings"), use_container_width=True)
