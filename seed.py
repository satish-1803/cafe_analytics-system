"""Loads the menu and ~2,500 synthetic orders so the dashboard has real patterns."""
import random, datetime as dt
from main import Session, MenuItem, Order, OrderItem, WaiterCall, Review, Base, engine

MENU = [
 ("Masala Chai", "Drinks", 40, "Ginger, cardamom, strong"), ("Cold Coffee", "Drinks", 120, "Thick, with ice cream"),
 ("Fresh Lime Soda", "Drinks", 70, "Sweet or salted"), ("Mango Lassi", "Drinks", 110, "Chilled, thick"),
 ("Veg Sandwich", "Snacks", 90, "Grilled, green chutney"), ("Paneer Tikka Roll", "Snacks", 150, "Smoky paneer, onion"),
 ("French Fries", "Snacks", 100, "Peri-peri dust"), ("Samosa (2 pc)", "Snacks", 40, "With tamarind chutney"),
 ("Paneer Butter Masala", "Mains", 240, "With 2 butter naan"), ("Veg Biryani", "Mains", 200, "Raita on the side"),
 ("Dal Tadka Rice", "Mains", 160, "Ghee tadka"), ("Gulab Jamun (2 pc)", "Dessert", 60, "Warm"),
 ("Brownie", "Dessert", 110, "Chocolate sauce")]
# lower weight = sells less often
W = [10, 6, 4, 4, 6, 5, 6, 8, 5, 5, 4, 3, 3]
HOUR_W = {8:2, 9:3, 10:3, 11:4, 12:9, 13:10, 14:6, 15:4, 16:6, 17:8, 18:10, 19:11, 20:8, 21:4}

def run(n=2500, days=60):
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    random.seed(7)
    with Session() as s:
        for name, cat, price, d in MENU:
            s.add(MenuItem(name=name, category=cat, price=price, description=d))
        s.commit()
        items = s.query(MenuItem).all()
        hours, hw = list(HOUR_W), list(HOUR_W.values())
        for _ in range(n):
            day = dt.datetime.utcnow().date() - dt.timedelta(days=random.randint(1, days))
            if day.weekday() >= 5 and random.random() < 0.3: day -= dt.timedelta(days=1)  # busier weekends
            t = dt.datetime.combine(day, dt.time(random.choices(hours, hw)[0], random.randint(0, 59)))
            o = Order(table_no=random.randint(1, 12), status="served", paid=True, created_at=t)
            for it in random.choices(items, W, k=random.choice([1, 2, 2, 3, 4])):
                o.items.append(OrderItem(item_id=it.id, name=it.name, qty=random.choice([1, 1, 1, 2]), price=it.price))
            s.add(o)
        s.commit()
        words = {5: ["Great chai!", "Quick service", "Loved the biryani"], 4: ["Good food, a bit slow", "Tasty"],
                 3: ["Okay", "Average"], 2: ["Fries were cold", "Too slow"], 1: ["Wrong order"]}
        for (oid,) in s.query(Order.id).all():
            if random.random() < 0.4:
                r = random.choices([5, 4, 3, 2, 1], [45, 30, 15, 7, 3])[0]
                s.add(Review(order_id=oid, rating=r, comment=random.choice(words[r])))
        s.commit()
    print("Seeded menu, orders and reviews")

if __name__ == "__main__": run()
