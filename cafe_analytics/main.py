import datetime as dt, os, hmac, hashlib, math, smtplib, ssl
from email.message import EmailMessage
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

engine = create_engine("sqlite:///cafe.db", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()
STATUSES = ["new", "preparing", "ready", "served"]

class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True)
    name = Column(String); category = Column(String)
    price = Column(Float); description = Column(String, default="")
    available = Column(Boolean, default=True)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    table_no = Column(Integer, index=True)
    status = Column(String, default="new")
    paid = Column(Boolean, default=False); tip = Column(Float, default=0)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    items = relationship("OrderItem", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    item_id = Column(Integer); name = Column(String)
    qty = Column(Integer); price = Column(Float)

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, index=True); rating = Column(Integer)
    comment = Column(String, default=""); created_at = Column(DateTime, default=dt.datetime.utcnow)

class WaiterCall(Base):
    __tablename__ = "waiter_calls"
    id = Column(Integer, primary_key=True)
    table_no = Column(Integer)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    done = Column(Boolean, default=False)

Base.metadata.create_all(engine)
app = FastAPI(title="QR Table Ordering")

SECRET = os.getenv("SECRET_KEY", "dev-secret-change-me")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")
def sign(v): return hmac.new(SECRET.encode(), v.encode(), hashlib.sha256).hexdigest()
def is_admin(req): return hmac.compare_digest(req.cookies.get("auth", ""), sign(ADMIN_USER))
def need_admin(req: Request):
    if not is_admin(req): raise HTTPException(401, "Login required")

class Hub:
    def __init__(self): self.clients = []
    async def connect(self, ws): await ws.accept(); self.clients.append(ws)
    async def push(self, kind):
        for ws in list(self.clients):
            try: await ws.send_json({"type": kind})
            except Exception: self.clients.remove(ws)
hub = Hub()

def order_json(o):
    return {"id": o.id, "table": o.table_no, "status": o.status, "paid": o.paid,
            "created_at": o.created_at.isoformat() + "Z",
            "total": sum(i.qty * i.price for i in o.items),
            "items": [{"name": i.name, "qty": i.qty} for i in o.items]}

class Line(BaseModel): item_id: int; qty: int
class NewOrder(BaseModel): table: int; items: list[Line]
class StatusIn(BaseModel): status: str
class CallIn(BaseModel): table: int

@app.get("/api/menu")
def menu():
    with Session() as s:
        return [dict(id=m.id, name=m.name, category=m.category, price=m.price,
                     description=m.description) for m in s.query(MenuItem).filter(MenuItem.available == True)]

@app.post("/api/orders")
async def place_order(body: NewOrder):
    with Session() as s:
        o = Order(table_no=body.table)
        for l in body.items:
            m = s.get(MenuItem, l.item_id)
            if m and m.available and 0 < l.qty <= 20:
                o.items.append(OrderItem(item_id=m.id, name=m.name, qty=l.qty, price=m.price))
        if not o.items: raise HTTPException(400, "Cart is empty")
        s.add(o); s.commit(); s.refresh(o); out = order_json(o)
    await hub.push("order"); return out

@app.get("/api/orders", dependencies=[Depends(need_admin)])
def active_orders():
    with Session() as s:
        q = s.query(Order).filter(Order.status != "served").order_by(Order.created_at)
        return [order_json(o) for o in q]

@app.get("/api/orders/{oid}")
def one_order(oid: int):
    with Session() as s:
        o = s.get(Order, oid)
        if not o: raise HTTPException(404, "Order not found")
        return order_json(o)

@app.patch("/api/orders/{oid}", dependencies=[Depends(need_admin)])
async def set_status(oid: int, body: StatusIn):
    if body.status not in STATUSES: raise HTTPException(400, "Bad status")
    with Session() as s:
        o = s.get(Order, oid)
        if not o: raise HTTPException(404, "Order not found")
        o.status = body.status; s.commit()
    await hub.push("update"); return {"ok": True}

@app.post("/api/calls")
async def call_waiter(body: CallIn):
    with Session() as s:
        s.add(WaiterCall(table_no=body.table)); s.commit()
    await hub.push("call"); return {"ok": True}

@app.get("/api/calls", dependencies=[Depends(need_admin)])
def calls():
    with Session() as s:
        return [{"id": c.id, "table": c.table_no} for c in
                s.query(WaiterCall).filter_by(done=False).order_by(WaiterCall.created_at)]

@app.patch("/api/calls/{cid}/done", dependencies=[Depends(need_admin)])
async def call_done(cid: int):
    with Session() as s:
        c = s.get(WaiterCall, cid)
        if c: c.done = True; s.commit()
    await hub.push("update"); return {"ok": True}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect:
        if ws in hub.clients: hub.clients.remove(ws)

@app.get("/t/{table}")
def table_page(table: int): return FileResponse("static/menu.html")
@app.get("/kitchen")
def kitchen_page(req: Request):
    return FileResponse("static/kitchen.html") if is_admin(req) else RedirectResponse("/login")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------- login + admin ----------------
class Login(BaseModel): username: str; password: str

@app.post("/api/login")
def login(b: Login):
    if not (hmac.compare_digest(b.username, ADMIN_USER) and hmac.compare_digest(b.password, ADMIN_PASS)):
        raise HTTPException(401, "Wrong username or password")
    r = JSONResponse({"ok": True}); r.set_cookie("auth", sign(ADMIN_USER), httponly=True, samesite="lax"); return r

@app.post("/api/logout")
def logout():
    r = JSONResponse({"ok": True}); r.delete_cookie("auth"); return r

@app.get("/login")
def login_page(): return FileResponse("static/login.html")

@app.get("/admin")
def admin_page(req: Request):
    return FileResponse("static/admin.html") if is_admin(req) else RedirectResponse("/login")

class MenuIn(BaseModel): name: str; category: str; price: float; description: str = ""
class MenuPatch(BaseModel):
    name: str | None = None; category: str | None = None; price: float | None = None
    description: str | None = None; available: bool | None = None

def mj(m): return dict(id=m.id, name=m.name, category=m.category, price=m.price,
                       description=m.description, available=m.available)

@app.get("/api/admin/menu", dependencies=[Depends(need_admin)])
def admin_menu():
    with Session() as s: return [mj(m) for m in s.query(MenuItem).order_by(MenuItem.category, MenuItem.id)]

@app.post("/api/admin/menu", dependencies=[Depends(need_admin)])
def add_item(b: MenuIn):
    if b.price < 0 or not b.name.strip(): raise HTTPException(400, "Name and a valid price are required")
    with Session() as s:
        m = MenuItem(name=b.name.strip(), category=b.category.strip(), price=b.price, description=b.description)
        s.add(m); s.commit(); return mj(m)

@app.patch("/api/admin/menu/{mid}", dependencies=[Depends(need_admin)])
def edit_item(mid: int, b: MenuPatch):
    with Session() as s:
        m = s.get(MenuItem, mid)
        if not m: raise HTTPException(404, "Item not found")
        for k, v in b.model_dump(exclude_none=True).items(): setattr(m, k, v)
        s.commit(); return mj(m)

@app.delete("/api/admin/menu/{mid}", dependencies=[Depends(need_admin)])
def delete_item(mid: int):
    with Session() as s:
        m = s.get(MenuItem, mid)
        if m: s.delete(m); s.commit()
    return {"ok": True}

# ---------------- bill split, tip, receipt ----------------
def send_receipt(to, body):
    host = os.getenv("SMTP_HOST")
    try:
        if not host:  # dev mode: save the receipt as a text file
            os.makedirs("receipts", exist_ok=True)
            name = to.replace("@", "_at_").replace("/", "_")
            with open(f"receipts/{name}_{int(dt.datetime.utcnow().timestamp())}.txt", "w", encoding="utf-8") as f: f.write(body)
            return
        m = EmailMessage(); m["Subject"] = "Your café receipt"; m["To"] = to
        m["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER"); m.set_content(body)
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as srv:
            srv.starttls(context=ssl.create_default_context())
            srv.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")); srv.send_message(m)
    except Exception as e: print("Receipt email failed:", e)

def unpaid(s, table):
    orders = s.query(Order).filter_by(table_no=table, paid=False).all()
    return orders, sum(i.qty * i.price for o in orders for i in o.items)

@app.get("/api/bill/{table}")
def get_bill(table: int):
    with Session() as s:
        orders, sub = unpaid(s, table)
        return {"subtotal": sub, "orders": [order_json(o) for o in orders]}

class PayIn(BaseModel): tip_pct: float = 0; split: int = 1; email: str = ""

@app.post("/api/bill/{table}/pay")
async def pay_bill(table: int, b: PayIn, bg: BackgroundTasks):
    if not (0 <= b.tip_pct <= 30 and 1 <= b.split <= 20): raise HTTPException(400, "Invalid tip or split")
    email = b.email.strip()
    if email and ("@" not in email or len(email) > 120): raise HTTPException(400, "Enter a valid email")
    with Session() as s:
        orders, sub = unpaid(s, table)
        if not orders: raise HTTPException(400, "Nothing to pay for this table")
        tip = round(sub * b.tip_pct / 100, 2); total = round(sub + tip, 2); share = math.ceil(total / b.split)
        lines = {}
        for o in orders:
            o.paid = True; o.tip = tip / len(orders)
            for i in o.items: lines[i.name] = lines.get(i.name, [0, i.price]); lines[i.name][0] += i.qty
        last = orders[-1].id; s.commit()
    body = f"Receipt - Table {table}\n\n" + "\n".join(f"{q} x {n}  Rs {q*p:.0f}" for n, (q, p) in lines.items())
    body += f"\n\nSubtotal: Rs {sub:.0f}\nTip ({b.tip_pct:g}%): Rs {tip:.2f}\nTotal: Rs {total:.2f}\nSplit {b.split} ways: Rs {share} each\n\nThank you!"
    if email: bg.add_task(send_receipt, email, body)
    await hub.push("update")
    return {"total": total, "share": share, "order_id": last, "emailed": bool(email)}

# ---------------- reviews ----------------
class ReviewIn(BaseModel): order_id: int; rating: int; comment: str = ""

@app.post("/api/reviews")
def add_review(b: ReviewIn):
    if not 1 <= b.rating <= 5: raise HTTPException(400, "Rating must be 1 to 5")
    with Session() as s:
        if not s.get(Order, b.order_id): raise HTTPException(404, "Order not found")
        if s.query(Review).filter_by(order_id=b.order_id).first(): raise HTTPException(400, "Already reviewed")
        s.add(Review(order_id=b.order_id, rating=b.rating, comment=b.comment[:500])); s.commit()
    return {"ok": True}

@app.get("/api/admin/reviews", dependencies=[Depends(need_admin)])
def reviews():
    with Session() as s:
        rs = s.query(Review).order_by(Review.created_at.desc()).all()
        avg = round(sum(r.rating for r in rs) / len(rs), 2) if rs else 0
        return {"avg": avg, "count": len(rs), "reviews": [
            {"order_id": r.order_id, "rating": r.rating, "comment": r.comment} for r in rs[:50]]}
