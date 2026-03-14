from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, date
import random
import string
import os
import smtplib
import time as _time_mod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template, session, redirect, url_for, request as flask_request, flash, redirect, url_for
# ─────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///coreinventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
import time as _time
app.config['SECRET_KEY'] = f'coreinventory-{int(_time.time())}'  

CORS(app)  

db = SQLAlchemy(app)


# ─────────────────────────────────────────
# MODELS (Database Tables)
# ─────────────────────────────────────────

class Product(db.Model):
    """Stores all inventory products."""
    __tablename__ = 'products'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    sku             = db.Column(db.String(50), unique=True, nullable=False)
    category        = db.Column(db.String(50), default='General')
    unit_of_measure = db.Column(db.String(20), default='Units')
    quantity_on_hand= db.Column(db.Float, default=0)
    reorder_level   = db.Column(db.Float, default=10)   # Alert if below this
    unit_cost       = db.Column(db.Float, default=0)

    def to_dict(self):
        return {
            'id':               self.id,
            'name':             self.name,
            'sku':              self.sku,
            'category':         self.category,
            'unit_of_measure':  self.unit_of_measure,
            'quantity_on_hand': self.quantity_on_hand,
            'reorder_level':    self.reorder_level,
            'unit_cost':        self.unit_cost,
            'is_low_stock':     self.quantity_on_hand <= self.reorder_level,
        }


class Operation(db.Model):
    """Receipts AND Deliveries — same table, filtered by operation_type."""
    __tablename__ = 'operations'

    id              = db.Column(db.Integer, primary_key=True)
    reference       = db.Column(db.String(50), unique=True, nullable=False)  
    operation_type  = db.Column(db.String(20), nullable=False) 
    partner_name    = db.Column(db.String(100))    
    scheduled_date  = db.Column(db.String(20))    # Date as string YYYY-MM-DD
    responsible     = db.Column(db.String(100), default='Admin')
    source_document = db.Column(db.String(100))    
    status          = db.Column(db.String(20), default='draft')   
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    notes           = db.Column(db.Text, default='')

    # Relationship to items
    items = db.relationship('OperationItem', backref='operation', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':               self.id,
            'reference':        self.reference,
            'operation_type':   self.operation_type,
            'partner_name':     self.partner_name,
            'scheduled_date':   self.scheduled_date,
            'responsible':      self.responsible,
            'source_document':  self.source_document,
            'status':           self.status,
            'created_at':       self.created_at.strftime('%Y-%m-%d %H:%M'),
            'notes':            self.notes,
            'items':            [item.to_dict() for item in self.items],
        }


class OperationItem(db.Model):
    """Individual product lines inside a receipt or delivery."""
    __tablename__ = 'operation_items'

    id                  = db.Column(db.Integer, primary_key=True)
    operation_id        = db.Column(db.Integer, db.ForeignKey('operations.id'), nullable=False)
    product_id          = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_demanded   = db.Column(db.Float, nullable=False)   # How many were ordered
    quantity_done       = db.Column(db.Float, default=0)        # How many were actually processed

    product = db.relationship('Product', backref='operation_items')

    def to_dict(self):
        # Format as [SKU] Name — exactly as shown in mockup e.g. [DESK001] Desk
        sku  = self.product.sku  if self.product else ''
        name = self.product.name if self.product else ''
        display_name = f'[{sku}] {name}' if sku else name
        return {
            'id':                 self.id,
            'operation_id':       self.operation_id,
            'product_id':         self.product_id,
            'product_name':       display_name,
            'product_name_plain': name,
            'product_sku':        sku,
            'quantity_demanded':  self.quantity_demanded,
            'quantity_done':      self.quantity_done,
            'quantity_on_hand':   self.product.quantity_on_hand if self.product else 0,
            'is_out_of_stock':    (self.product.quantity_on_hand <= 0) if self.product else False,
        }


class StockLedger(db.Model):
    """Logs every single stock movement. This is the Move History page."""
    __tablename__ = 'stock_ledger'

    id              = db.Column(db.Integer, primary_key=True)
    product_id      = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    operation_id    = db.Column(db.Integer, db.ForeignKey('operations.id'), nullable=True)
    movement_type   = db.Column(db.String(20))   # 'IN', 'OUT', 'ADJUST'
    from_location   = db.Column(db.String(100), default='')
    to_location     = db.Column(db.String(100), default='')
    quantity        = db.Column(db.Float)         # Positive for IN, negative for OUT
    timestamp       = db.Column(db.DateTime, default=datetime.utcnow)
    reference       = db.Column(db.String(50))   # e.g. WH/IN/001

    product   = db.relationship('Product')
    operation = db.relationship('Operation')

    def to_dict(self):
        # Get contact (partner_name) and status from linked operation
        contact = ''
        status  = 'done'
        date_str = self.timestamp.strftime('%d/%m/%Y') if self.timestamp else ''
        if self.operation:
            contact  = self.operation.partner_name or ''
            status   = self.operation.status
        return {
            'id':             self.id,
            'product_id':     self.product_id,
            'product_name':   self.product.name if self.product else '—',
            'operation_id':   self.operation_id,
            'movement_type':  self.movement_type,
            'from_location':  self.from_location or '—',
            'to_location':    self.to_location   or '—',
            'quantity':       self.quantity,
            'timestamp':      self.timestamp.strftime('%Y-%m-%d %H:%M'),
            'date':           date_str,
            'reference':      self.reference or '—',
            'contact':        contact,
            'status':         status,
        }



class User(db.Model):
    """User accounts for login/signup."""
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)
    login_id   = db.Column(db.String(12), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)  # plain for hackathon
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'login_id': self.login_id, 'email': self.email}


class Warehouse(db.Model):
    """Warehouse — Name, Short Code, Address."""
    __tablename__ = 'warehouses'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, default='Main Warehouse')
    short_code = db.Column(db.String(10),  nullable=False, default='WH')
    address    = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id':self.id,'name':self.name,'short_code':self.short_code,'address':self.address}


class Location(db.Model):
    """Sub-locations inside a warehouse — rooms, racks, etc."""
    __tablename__ = 'locations'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), nullable=False)
    short_code   = db.Column(db.String(20),  nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=True)
    warehouse    = db.relationship('Warehouse', backref='locations')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':self.id,'name':self.name,'short_code':self.short_code,
            'warehouse_id':self.warehouse_id,
            'warehouse_name':self.warehouse.name if self.warehouse else ''
        }

# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────

def generate_reference(operation_type):
    """
    Generate reference exactly matching mockup format:
    WH/IN/0001  for receipts
    WH/OUT/0001 for deliveries
    <Warehouse>/<Operation>/<ID> — auto-incremented unique id
    """
    prefix = 'WH/IN' if operation_type == 'receipt' else 'WH/OUT'
    count  = Operation.query.filter_by(operation_type=operation_type).count() + 1
    return f"{prefix}/{str(count).zfill(4)}"


def log_movement(product_id, operation_id, movement_type, quantity, reference, from_loc='', to_loc=''):
    """Insert a row into stock_ledger whenever stock changes."""
    entry = StockLedger(
        product_id    = product_id,
        operation_id  = operation_id,
        movement_type = movement_type,
        from_location = from_loc,
        to_location   = to_loc,
        quantity      = quantity,
        reference     = reference,
    )
    db.session.add(entry)


# ─────────────────────────────────────────
# ROUTES — DASHBOARD
# ─────────────────────────────────────────

@app.route('/api/dashboard')
def dashboard():
    """
    Dashboard KPIs — exactly matching mockup:
    Receipt card: to_receive, late, operations counts
    Delivery card: to_deliver, late, waiting, operations counts
    Late      = scheduled_date < today (overdue)
    Operations= scheduled_date > today (upcoming)
    Waiting   = status='waiting' (waiting for stock)
    """
    from datetime import date as date_type
    today = date_type.today().isoformat()

    # ── RECEIPTS ──────────────────────────────────────────
    r_base = Operation.query.filter_by(operation_type='receipt').filter(
        Operation.status.in_(['draft','waiting','ready'])
    )
    r_to_receive  = r_base.count()
    r_late        = r_base.filter(Operation.scheduled_date < today).count()
    r_operations  = r_base.filter(Operation.scheduled_date > today).count()

    # ── DELIVERIES ────────────────────────────────────────
    d_base = Operation.query.filter_by(operation_type='delivery').filter(
        Operation.status.in_(['draft','waiting','ready'])
    )
    d_to_deliver  = d_base.count()
    d_late        = d_base.filter(Operation.scheduled_date < today).count()
    d_waiting     = Operation.query.filter_by(operation_type='delivery', status='waiting').count()
    d_operations  = d_base.filter(Operation.scheduled_date > today).count()

    # ── STOCK & RECENT ────────────────────────────────────
    total_products     = Product.query.count()
    low_stock_count    = Product.query.filter(Product.quantity_on_hand <= Product.reorder_level).count()
    low_stock_products = Product.query.filter(Product.quantity_on_hand <= Product.reorder_level).all()
    recent_movements   = StockLedger.query.order_by(StockLedger.timestamp.desc()).limit(10).all()

    return jsonify({
        # Receipt card
        'receipt_to_receive':  r_to_receive,
        'receipt_late':        r_late,
        'receipt_operations':  r_operations,
        # Delivery card
        'delivery_to_deliver': d_to_deliver,
        'delivery_late':       d_late,
        'delivery_waiting':    d_waiting,
        'delivery_operations': d_operations,
        # Legacy fields (keep for compatibility)
        'pending_receipts':    r_to_receive,
        'pending_deliveries':  d_to_deliver,
        'total_products':      total_products,
        'low_stock_count':     low_stock_count,
        'low_stock_products':  [p.to_dict() for p in low_stock_products],
        'recent_movements':    [m.to_dict() for m in recent_movements],
    })


# ─────────────────────────────────────────
# ROUTES — PRODUCTS
# ─────────────────────────────────────────

@app.route('/api/products', methods=['GET'])
def get_products():
    """Return all products. Optional ?category= filter."""
    category = request.args.get('category')
    query    = Product.query
    if category:
        query = query.filter_by(category=category)
    products = query.order_by(Product.name).all()
    return jsonify([p.to_dict() for p in products])


@app.route('/api/products/low-stock', methods=['GET'])
def get_low_stock():
    """Return only products at or below their reorder level."""
    products = Product.query.filter(
        Product.quantity_on_hand <= Product.reorder_level
    ).all()
    return jsonify([p.to_dict() for p in products])


@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Return a single product by ID."""
    product = Product.query.get_or_404(product_id)
    return jsonify(product.to_dict())


@app.route('/api/products', methods=['POST'])
def create_product():
    """
    Create a new product.
    Expects JSON: { name, sku, category, unit_of_measure, quantity_on_hand, reorder_level, unit_cost }
    """
    data = request.get_json()

    # Validate required fields
    if not data.get('name') or not data.get('sku'):
        return jsonify({'error': 'Name and SKU are required'}), 400

    # Check SKU is unique
    if Product.query.filter_by(sku=data['sku']).first():
        return jsonify({'error': 'SKU already exists'}), 400

    product = Product(
        name             = data['name'],
        sku              = data['sku'],
        category         = data.get('category', 'General'),
        unit_of_measure  = data.get('unit_of_measure', 'Units'),
        quantity_on_hand = float(data.get('quantity_on_hand', 0)),
        reorder_level    = float(data.get('reorder_level', 10)),
        unit_cost        = float(data.get('unit_cost', 0)),
    )
    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update product details (not stock quantity — use operations for that)."""
    product = Product.query.get_or_404(product_id)
    data    = request.get_json()

    product.name             = data.get('name',             product.name)
    product.category         = data.get('category',         product.category)
    product.unit_of_measure  = data.get('unit_of_measure',  product.unit_of_measure)
    product.reorder_level    = float(data.get('reorder_level', product.reorder_level))
    product.unit_cost        = float(data.get('unit_cost',     product.unit_cost))

    db.session.commit()
    return jsonify(product.to_dict())


@app.route('/api/products/<int:product_id>/adjust', methods=['POST'])
def adjust_stock(product_id):
    """
    Manual stock adjustment (from the Products/Stock page).
    Use when physical count differs from system count.
    Expects JSON: { quantity, reason }
    """
    product = Product.query.get_or_404(product_id)
    data    = request.get_json()

    new_qty    = float(data.get('quantity', product.quantity_on_hand))
    difference = new_qty - product.quantity_on_hand
    reason     = data.get('reason', 'Manual adjustment')

    product.quantity_on_hand = new_qty

    # Log the adjustment in the ledger
    log_movement(
        product_id    = product.id,
        operation_id  = None,
        movement_type = 'ADJUST',
        quantity      = difference,
        reference     = f'ADJ/{product.id}/{datetime.now().strftime("%d%m%H%M")}',
        from_loc      = 'Stock',
        to_loc        = 'Stock',
    )
    db.session.commit()
    return jsonify({'message': reason, 'product': product.to_dict()})


# ─────────────────────────────────────────
# ROUTES — OPERATIONS (Receipts & Deliveries)
# ─────────────────────────────────────────

@app.route('/api/operations', methods=['GET'])
def get_operations():
    """
    List all operations.
    Use ?type=receipt or ?type=delivery to filter.
    Use ?status=draft to filter by status.
    """
    op_type = request.args.get('type')
    status  = request.args.get('status')
    search  = request.args.get('search', '')

    query = Operation.query
    if op_type:
        query = query.filter_by(operation_type=op_type)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(
            db.or_(
                Operation.reference.ilike(f'%{search}%'),
                Operation.partner_name.ilike(f'%{search}%'),
            )
        )

    operations = query.order_by(Operation.created_at.desc()).all()
    return jsonify([op.to_dict() for op in operations])


@app.route('/api/operations/<int:op_id>', methods=['GET'])
def get_operation(op_id):
    """Get a single operation with all its items."""
    op = Operation.query.get_or_404(op_id)
    return jsonify(op.to_dict())


@app.route('/api/operations', methods=['POST'])
def create_operation():
    """
    Create a new receipt or delivery (in draft status).
    Expects JSON: { operation_type, partner_name, scheduled_date, responsible, source_document, notes }
    """
    data    = request.get_json()
    op_type = data.get('operation_type')

    if op_type not in ('receipt', 'delivery'):
        return jsonify({'error': 'operation_type must be receipt or delivery'}), 400

    operation = Operation(
        reference       = generate_reference(op_type),
        operation_type  = op_type,
        partner_name    = data.get('partner_name', ''),
        scheduled_date  = data.get('scheduled_date', date.today().isoformat()),
        responsible     = data.get('responsible', 'Admin'),
        source_document = data.get('source_document', ''),
        notes           = data.get('notes', ''),
        status          = 'draft',
    )
    db.session.add(operation)
    db.session.commit()
    return jsonify(operation.to_dict()), 201


@app.route('/api/operations/<int:op_id>/items', methods=['POST'])
def add_item_to_operation(op_id):
    """
    Add a product line to an existing operation.
    Expects JSON: { product_id, quantity_demanded }
    """
    op   = Operation.query.get_or_404(op_id)
    data = request.get_json()

    if op.status == 'done':
        return jsonify({'error': 'Cannot modify a completed operation'}), 400

    product = Product.query.get(data.get('product_id'))
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    qty = float(data.get('quantity_demanded', 0))
    if qty <= 0:
        return jsonify({'error': 'Quantity must be greater than 0'}), 400

    item = OperationItem(
        operation_id      = op.id,
        product_id        = product.id,
        quantity_demanded = qty,
        quantity_done     = qty,  # Default done = demanded for simplicity
    )
    db.session.add(item)

    # Move status to 'ready' if it was draft
    if op.status == 'draft':
        op.status = 'ready'

    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route('/api/operations/<int:op_id>/items/<int:item_id>', methods=['DELETE'])
def remove_item_from_operation(op_id, item_id):
    """Remove a product line from a draft operation."""
    item = OperationItem.query.filter_by(id=item_id, operation_id=op_id).first_or_404()
    op   = item.operation

    if op.status == 'done':
        return jsonify({'error': 'Cannot modify a completed operation'}), 400

    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Item removed'})


@app.route('/api/operations/<int:op_id>/validate', methods=['POST'])
def validate_operation(op_id):
    """
    THE CORE BUSINESS LOGIC.
    
    For RECEIPT:  Each product's stock INCREASES. Log IN to ledger.
    For DELIVERY: Check stock first. If enough, DECREASE stock. Log OUT to ledger.
    
    Sets status to 'done' after successful validation.
    """
    op = Operation.query.get_or_404(op_id)

    # Cannot validate an already completed or cancelled operation
    if op.status == 'done':
        return jsonify({'error': 'Operation is already completed'}), 400
    if op.status == 'cancelled':
        return jsonify({'error': 'Operation is cancelled'}), 400
    if not op.items:
        return jsonify({'error': 'Cannot validate an empty operation — add products first'}), 400

    # ── RECEIPT: stock comes IN ──────────────────────────────────────────
    if op.operation_type == 'receipt':
        for item in op.items:
            product = item.product

            # Increase stock by quantity_done
            product.quantity_on_hand += item.quantity_done

            # Log the inbound movement
            log_movement(
                product_id   = product.id,
                operation_id = op.id,
                movement_type= 'IN',
                quantity     = +item.quantity_done,   # Positive = stock increased
                reference    = op.reference,
                from_loc     = op.partner_name or 'Vendor',
                to_loc       = 'WH/Stock',
            )

    # ── DELIVERY: stock goes OUT ─────────────────────────────────────────
    elif op.operation_type == 'delivery': 
        for item in op.items:
            product = item.product
            if product.quantity_on_hand < item.quantity_demanded:
                return jsonify({
                    'error': f'Insufficient stock for "{product.name}". '
                             f'Available: {product.quantity_on_hand} {product.unit_of_measure}, '
                             f'Requested: {item.quantity_demanded} {product.unit_of_measure}'
                }), 400

        for item in op.items:
            product = item.product
            product.quantity_on_hand -= item.quantity_demanded
            item.quantity_done        = item.quantity_demanded

            log_movement(
                product_id   = product.id,
                operation_id = op.id,
                movement_type= 'OUT',
                quantity     = -item.quantity_demanded,   # Negative = stock decreased
                reference    = op.reference,
                from_loc     = 'WH/Stock',
                to_loc       = op.partner_name or 'Customer',
            )

    op.status = 'done'
    db.session.commit()

    return jsonify({
        'message':   f'Operation {op.reference} validated successfully',
        'operation': op.to_dict(),
    })




@app.route('/api/operations/<int:op_id>/waiting', methods=['POST'])
def mark_waiting(op_id):
    """Move delivery from Draft to Waiting (waiting for out of stock products)."""
    op = Operation.query.get_or_404(op_id)
    if op.status != 'draft':
        return jsonify({'error': 'Only draft operations can be marked waiting'}), 400
    op.status = 'waiting'
    db.session.commit()
    return jsonify({'message': f'{op.reference} marked as Waiting', 'operation': op.to_dict()})

@app.route('/api/operations/<int:op_id>/ready', methods=['POST'])
def mark_ready(op_id):
    """Move operation from Draft to Ready status (TO DO → Ready in mockup)."""
    op = Operation.query.get_or_404(op_id)
    if op.status != 'draft':
        return jsonify({'error': 'Only draft operations can be marked ready'}), 400
    op.status = 'ready'
    db.session.commit()
    return jsonify({'message': f'{op.reference} marked as Ready', 'operation': op.to_dict()})

@app.route('/api/operations/<int:op_id>/cancel', methods=['POST'])
def cancel_operation(op_id):
    """Cancel a draft/waiting/ready operation. Cannot cancel a done operation."""
    op = Operation.query.get_or_404(op_id)

    if op.status == 'done':
        return jsonify({'error': 'Cannot cancel a completed operation'}), 400

    op.status = 'cancelled'
    db.session.commit()
    return jsonify({'message': f'Operation {op.reference} cancelled', 'operation': op.to_dict()})


# ─────────────────────────────────────────
# ROUTES — STOCK LEDGER (Move History)
# ─────────────────────────────────────────

@app.route('/api/stock-ledger', methods=['GET'])
def get_stock_ledger():
    """
    Return all stock movements (the Move History page).
    Optional ?search= to filter by product name or reference.
    Optional ?product_id= to filter by specific product.
    """
    search     = request.args.get('search', '')
    product_id = request.args.get('product_id')

    query = StockLedger.query

    if product_id:
        query = query.filter_by(product_id=product_id)

    if search:
        query = query.join(Product).filter(
            db.or_(
                StockLedger.reference.ilike(f'%{search}%'),
                Product.name.ilike(f'%{search}%'),
            )
        )

    movements = query.order_by(StockLedger.timestamp.desc()).all()
    return jsonify([m.to_dict() for m in movements])


# ─────────────────────────────────────────
# DATABASE INIT + SAMPLE DATA
# ─────────────────────────────────────────

def seed_sample_data():
    """Add 5 sample products and default admin user if empty."""
    # Seed default admin user
    if not User.query.filter_by(login_id='admin').first():
        admin = User(login_id='admin', email='admin@coreinventory.com', password='Admin@123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Default user: admin / Admin@123")

    if Product.query.count() > 0:
        return  # Already seeded

    sample_products = [
        Product(name='Steel Rods',       sku='SKU-001', category='Raw Materials',  unit_of_measure='Kg',    quantity_on_hand=150, reorder_level=30,  unit_cost=400),
        Product(name='Office Chairs',    sku='SKU-002', category='Furniture',      unit_of_measure='Units', quantity_on_hand=40,  reorder_level=10,  unit_cost=3500),
        Product(name='Copper Wire',      sku='SKU-003', category='Electrical',     unit_of_measure='Meters',quantity_on_hand=8,   reorder_level=20,  unit_cost=150),  # Low stock!
        Product(name='Cardboard Boxes',  sku='SKU-004', category='Packaging',      unit_of_measure='Units', quantity_on_hand=500, reorder_level=100, unit_cost=25),
        Product(name='Laptop Stand',     sku='SKU-005', category='Electronics',    unit_of_measure='Units', quantity_on_hand=5,   reorder_level=10,  unit_cost=1200), # Low stock!
    ]

    db.session.add_all(sample_products)
    db.session.commit()
    print("✅ Sample products added!")

    # Seed default warehouse
    if Warehouse.query.count() == 0:
        wh = Warehouse(name='Main Warehouse', short_code='WH', address='Indus University, Rancharda, Ahmedabad - 382115')
        db.session.add(wh)
        db.session.commit()
        # Seed default locations
        locs = [
            Location(name='Stock',           short_code='WH/STOCK', warehouse_id=wh.id),
            Location(name='Production Floor',short_code='WH/PROD',  warehouse_id=wh.id),
            Location(name='Rack A',          short_code='WH/RACK-A',warehouse_id=wh.id),
        ]
        db.session.add_all(locs)
        db.session.commit()
        print("✅ Default warehouse + locations seeded")

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """
    Delete a product permanently.
    Strategy: also delete any linked operation_items so the product can be removed.
    Stock ledger entries are kept for historical record but product reference becomes null.
    """
    product = Product.query.get_or_404(product_id)

    OperationItem.query.filter_by(product_id=product_id).delete()

    StockLedger.query.filter_by(product_id=product_id).update({'product_id': None})

    db.session.delete(product)
    db.session.commit()
    return jsonify({'message': f'"{product.name}" deleted successfully.'})


# ─────────────────────────────────────────
# AUTH API ROUTES
# ─────────────────────────────────────────

@app.route('/api/signup', methods=['POST'])
def api_signup():
    """Register a new user with validation."""
    data     = flask_request.get_json()
    login_id = (data.get('login_id') or '').strip()
    email    = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '')
    confirm  = (data.get('confirm_password') or '')

    # Validate login ID: 6-12 chars, unique
    if not (6 <= len(login_id) <= 12):
        return jsonify({'error': 'Login ID must be between 6 and 12 characters.'}), 400
    if User.query.filter_by(login_id=login_id).first():
        return jsonify({'error': 'Login ID already taken. Choose another.'}), 400

    # Validate email: unique
    if not email or '@' not in email:
        return jsonify({'error': 'Enter a valid email address.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered. Please login.'}), 400

    # Validate password: 8+ chars, uppercase, lowercase, special char
    import re
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters.'}), 400
    if not re.search(r'[A-Z]', password):
        return jsonify({'error': 'Password must contain at least one uppercase letter.'}), 400
    if not re.search(r'[a-z]', password):
        return jsonify({'error': 'Password must contain at least one lowercase letter.'}), 400
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-]', password):
        return jsonify({'error': 'Password must contain at least one special character.'}), 400
    if password != confirm:
        return jsonify({'error': 'Passwords do not match.'}), 400

    user = User(login_id=login_id, email=email, password=password)
    db.session.add(user)
    db.session.commit()
    session['user_id']  = user.id
    session['login_id'] = user.login_id
    return jsonify({'message': 'Account created!', 'user': user.to_dict()}), 201


@app.route('/api/login', methods=['POST'])
def api_login():
    """Login with login_id + password."""
    data     = flask_request.get_json()
    login_id = (data.get('login_id') or '').strip()
    password = (data.get('password') or '')

    user = User.query.filter_by(login_id=login_id, password=password).first()
    if not user:
        return jsonify({'error': 'Invalid Login ID or Password.'}), 401

    session['user_id']  = user.id
    session['login_id'] = user.login_id
    return jsonify({'message': 'Login successful', 'user': user.to_dict()})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Clear session."""
    session.clear()
    return jsonify({'message': 'Logged out'})


@app.route('/api/me')
def api_me():
    """Return current logged-in user."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict())


@app.route('/api/reset-password', methods=['POST'])
def api_reset_password():
    """Reset password by verifying login_id + email match."""
    data      = flask_request.get_json()
    login_id  = (data.get('login_id') or '').strip()
    email     = (data.get('email') or '').strip().lower()
    new_pw    = (data.get('new_password') or '')

    user = User.query.filter_by(login_id=login_id, email=email).first()
    if not user:
        return jsonify({'error': 'No account found with that Login ID and email combination.'}), 404

    if len(new_pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters.'}), 400

    user.password = new_pw
    db.session.commit()
    return jsonify({'message': 'Password reset successfully.'})


# ─────────────────────────────────────────
# OTP — In-memory store  {email: {otp, expires_at, login_id}}
# ─────────────────────────────────────────

_otp_store = {}   

SMTP_EMAIL    = os.environ.get('SMTP_EMAIL', '')      # your gmail
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')   # gmail app password

def _send_otp_email(to_email, otp, login_id):
    """Send OTP email via Gmail SMTP."""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Inventify — Your OTP for Password Reset'
    msg['From']    = SMTP_EMAIL
    msg['To']      = to_email

    html = f"""
    <div style="font-family:'DM Sans',sans-serif;max-width:480px;margin:0 auto;background:#0f172a;border-radius:16px;padding:32px;color:#f1f5f9;">
      <div style="text-align:center;margin-bottom:24px;">
        <div style="font-size:24px;font-weight:800;color:#10b981;">Inventify</div>
        <div style="font-size:12px;color:#64748b;margin-top:2px;">AI Inventory OS</div>
      </div>
      <h2 style="font-size:18px;font-weight:700;margin-bottom:8px;">Password Reset OTP</h2>
      <p style="font-size:13px;color:#94a3b8;margin-bottom:24px;">
        Hi <strong style="color:#f1f5f9;">{login_id}</strong>, use the OTP below to reset your password.
        This code expires in <strong style="color:#f59e0b;">10 minutes</strong>.
      </p>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px;">
        <div style="font-size:38px;font-weight:900;letter-spacing:12px;color:#10b981;font-family:monospace;">{otp}</div>
      </div>
      <p style="font-size:12px;color:#475569;">
        If you did not request this, ignore this email. Your password will not change.
      </p>
      <hr style="border:none;border-top:1px solid #334155;margin:20px 0;">
      <p style="font-size:11px;color:#334155;text-align:center;">Inventify · AI Inventory OS</p>
    </div>
    """
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, to_email, msg.as_string())


@app.route('/api/otp/send', methods=['POST'])
def api_otp_send():
    """Step 1 — Verify login_id + email exist, generate OTP, send email."""
    data     = flask_request.get_json(force=True) or {}
    login_id = (data.get('login_id') or '').strip()
    email    = (data.get('email')    or '').strip().lower()

    if not login_id or not email:
        return jsonify({'error': 'Login ID and email are required.'}), 400

    user = User.query.filter_by(login_id=login_id, email=email).first()
    if not user:
        return jsonify({'error': 'No account found with that Login ID and email.'}), 404

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))

    # Store with 10-min expiry
    _otp_store[email] = {
        'otp':      otp,
        'expires':  _time_mod.time() + 600,   # 10 minutes
        'login_id': login_id,
    }

    smtp_email = os.environ.get('SMTP_EMAIL', '')
    smtp_pass  = os.environ.get('SMTP_PASSWORD', '')

    if smtp_email and smtp_pass:
        try:
            _send_otp_email(email, otp, login_id)
        except Exception as e:
            return jsonify({'error': f'Failed to send email: {str(e)}'}), 500
    else:
        print(f"\n{'='*40}\n📧 DEV MODE OTP for {email}: {otp}\n{'='*40}\n")

    return jsonify({'message': 'OTP sent successfully.', 'dev_otp': otp if not smtp_email else None})


@app.route('/api/otp/verify', methods=['POST'])
def api_otp_verify():
    """Step 2 — Verify the OTP entered by user."""
    data  = flask_request.get_json(force=True) or {}
    email = (data.get('email') or '').strip().lower()
    otp   = (data.get('otp')   or '').strip()

    if not email or not otp:
        return jsonify({'error': 'Email and OTP are required.'}), 400

    record = _otp_store.get(email)
    if not record:
        return jsonify({'error': 'OTP not found. Please request a new one.'}), 400

    if _time_mod.time() > record['expires']:
        _otp_store.pop(email, None)
        return jsonify({'error': 'OTP has expired. Please request a new one.'}), 400

    if record['otp'] != otp:
        return jsonify({'error': 'Incorrect OTP. Please try again.'}), 400

    record['verified'] = True
    record['expires']  = _time_mod.time() + 300  # 5 more mins to set password

    return jsonify({'message': 'OTP verified successfully.'})


@app.route('/api/otp/reset-password', methods=['POST'])
def api_otp_reset_password():
    """Step 3 — Set new password after OTP verified."""
    data     = flask_request.get_json(force=True) or {}
    email    = (data.get('email')        or '').strip().lower()
    new_pw   = (data.get('new_password') or '')

    if not email or not new_pw:
        return jsonify({'error': 'Email and new password are required.'}), 400

    record = _otp_store.get(email)
    if not record or not record.get('verified'):
        return jsonify({'error': 'OTP not verified. Please complete verification first.'}), 400

    if _time_mod.time() > record['expires']:
        _otp_store.pop(email, None)
        return jsonify({'error': 'Session expired. Please start over.'}), 400

    if len(new_pw) < 8:
        return jsonify({'error': 'Password must be at least 8 characters.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    user.password = new_pw
    db.session.commit()
    _otp_store.pop(email, None)   # Clear OTP after successful reset

    return jsonify({'message': 'Password reset successfully.'})


@app.route('/api/stock-summary', methods=['GET'])
def stock_summary():
    """
    Returns stock view exactly matching mockup:
    Product, per unit cost, On Hand, Free to Use
    Free to Use = On Hand - reserved (pending delivery qty)
    """
    products = Product.query.order_by(Product.name).all()
    result   = []

    for p in products:
        # Calculate reserved = qty in pending delivery operations
        from sqlalchemy import func
        reserved = db.session.query(
            func.coalesce(func.sum(OperationItem.quantity_demanded), 0)
        ).join(Operation).filter(
            OperationItem.product_id == p.id,
            Operation.operation_type == 'delivery',
            Operation.status.in_(['draft','waiting','ready'])
        ).scalar() or 0

        free_to_use = max(0, p.quantity_on_hand - reserved)

        result.append({
            'id':           p.id,
            'name':         p.name,
            'sku':          p.sku,
            'unit_cost':    p.unit_cost,
            'on_hand':      p.quantity_on_hand,
            'reserved':     reserved,
            'free_to_use':  free_to_use,
            'unit_of_measure': p.unit_of_measure,
            'reorder_level':p.reorder_level,
            'is_low_stock': p.quantity_on_hand <= p.reorder_level,
        })

    return jsonify(result)


# ─────────────────────────────────────────
# SETTINGS API — Warehouse & Location
# ─────────────────────────────────────────

@app.route('/api/warehouses', methods=['GET'])
def get_warehouses():
    return jsonify([w.to_dict() for w in Warehouse.query.all()])

@app.route('/api/warehouses', methods=['POST'])
def create_warehouse():
    data = flask_request.get_json()
    if not data.get('name'):
        return jsonify({'error':'Name is required'}), 400
    wh = Warehouse(
        name       = data['name'].strip(),
        short_code = data.get('short_code','WH').strip().upper(),
        address    = data.get('address','').strip()
    )
    db.session.add(wh)
    db.session.commit()
    return jsonify(wh.to_dict()), 201

@app.route('/api/warehouses/<int:wh_id>', methods=['PUT'])
def update_warehouse(wh_id):
    wh   = Warehouse.query.get_or_404(wh_id)
    data = flask_request.get_json()
    wh.name       = data.get('name',       wh.name).strip()
    wh.short_code = data.get('short_code', wh.short_code).strip().upper()
    wh.address    = data.get('address',    wh.address).strip()
    db.session.commit()
    return jsonify(wh.to_dict())

@app.route('/api/warehouses/<int:wh_id>', methods=['DELETE'])
def delete_warehouse(wh_id):
    wh = Warehouse.query.get_or_404(wh_id)
    db.session.delete(wh)
    db.session.commit()
    return jsonify({'message':'Deleted'})

@app.route('/api/locations', methods=['GET'])
def get_locations():
    wh_id = flask_request.args.get('warehouse_id')
    q     = Location.query
    if wh_id: q = q.filter_by(warehouse_id=int(wh_id))
    return jsonify([l.to_dict() for l in q.order_by(Location.name).all()])

@app.route('/api/locations', methods=['POST'])
def create_location():
    data = flask_request.get_json()
    if not data.get('name'):
        return jsonify({'error':'Name is required'}), 400
    if not data.get('short_code'):
        return jsonify({'error':'Short Code is required'}), 400
    loc = Location(
        name         = data['name'].strip(),
        short_code   = data['short_code'].strip().upper(),
        warehouse_id = data.get('warehouse_id') or None
    )
    db.session.add(loc)
    db.session.commit()
    return jsonify(loc.to_dict()), 201

@app.route('/api/locations/<int:loc_id>', methods=['PUT'])
def update_location(loc_id):
    loc  = Location.query.get_or_404(loc_id)
    data = flask_request.get_json()
    loc.name         = data.get('name',         loc.name).strip()
    loc.short_code   = data.get('short_code',   loc.short_code).strip().upper()
    loc.warehouse_id = data.get('warehouse_id', loc.warehouse_id)
    db.session.commit()
    return jsonify(loc.to_dict())

@app.route('/api/locations/<int:loc_id>', methods=['DELETE'])
def delete_location(loc_id):
    loc = Location.query.get_or_404(loc_id)
    db.session.delete(loc)
    db.session.commit()
    return jsonify({'message':'Deleted'})


#page routes

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect('/')
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    if 'user_id' in session:
        return redirect('/')
    return render_template('signup.html')

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

    if 'user_id' in session:
        return redirect('/')
    return render_template('signup.html')




# ── Auth helper ──────────────────────────────
def get_current_user():
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
@login_required
def dashboard_page():
    user = get_current_user()
    return render_template('dashboard.html', current_user=user)

@app.route('/products')
@login_required
def products_page():
    user = get_current_user()
    return render_template('products.html', current_user=user)

@app.route('/receipts')
@login_required
def receipts_page():
    user = get_current_user()
    return render_template('receipts.html', current_user=user)

@app.route('/receipts/<int:op_id>')
@login_required
def receipt_detail_page(op_id):
    user = get_current_user()
    return render_template('receipt_detail.html', op_id=op_id, current_user=user)

@app.route('/deliveries')
@login_required
def deliveries_page():
    user = get_current_user()
    return render_template('deliveries.html', current_user=user)

@app.route('/deliveries/<int:op_id>')
@login_required
def delivery_detail_page(op_id):
    user = get_current_user()
    return render_template('delivery_detail.html', op_id=op_id, current_user=user)

@app.route('/move-history')
@login_required
def move_history_page():
    user = get_current_user()
    return render_template('move_history.html', current_user=user)

@app.route('/stock')
@login_required
def stock_page():
    user = get_current_user()
    return render_template('stock.html', current_user=user)

@app.route('/adjustments')
@login_required
def adjustments_page():
    user = get_current_user()
    return render_template('adjustments.html', current_user=user)

@app.route('/settings')
@login_required
def settings_page():
    user = get_current_user()
    return render_template('settings.html', current_user=user)

@app.route('/intelligence')
@login_required
def intelligence_page():
    user = get_current_user()
    return render_template('intelligence.html', current_user=user)



# ─────────────────────────────────────────
# ROUTES — AI INSIGHTS (Claude API Proxy)
# ─────────────────────────────────────────

@app.route('/api/ai-insights', methods=['POST'])
def ai_insights():
    """
    Server-side proxy for Gemini API.
    Receives inventory data summary from frontend,
    calls Gemini, returns narrative insights.
    """
    import urllib.request
    import json as _json
    import os

    try:
        payload = request.get_json(force=True) or {}
        data_context = payload.get('data_context', '')

        if not data_context:
            return jsonify({'error': 'No data context provided'}), 400

        # ── Build prompt ──────────────────────────────────────────
        prompt = f"""You are an expert inventory analyst for StockSense, a warehouse management system.

Based on the following real-time inventory data, provide a concise, actionable intelligence report with exactly 4 bullet points. Each bullet should be a specific, data-driven insight or recommendation. Be direct, practical, and use the actual product names and numbers from the data.

{data_context}

Respond with exactly 4 bullet points, each starting with a relevant emoji, then the insight. No headers, no intro text, just the 4 bullets separated by newlines."""

        # ── Call Gemini API ────────────────────────────────────────
        GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

        gemini_payload = _json.dumps({
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }).encode('utf-8')

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

        req = urllib.request.Request(
            url,
            data=gemini_payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            result = _json.loads(resp.read().decode('utf-8'))

        text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        return jsonify({'insights': lines, 'source': 'gemini'})

    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')
        return jsonify({'insights': _rule_based_insights(), 'source': 'fallback', 'error': err_body})
    except Exception as e:
        return jsonify({'insights': _rule_based_insights(), 'source': 'fallback', 'error': str(e)})


def _rule_based_insights():
    """Generate insights purely from DB data — no external API needed."""
    from datetime import date as _date, timedelta

    today = _date.today()
    week_ago = (today - timedelta(days=7)).isoformat()

    total   = Product.query.count()
    low     = Product.query.filter(Product.quantity_on_hand <= Product.reorder_level).count()
    out     = Product.query.filter(Product.quantity_on_hand <= 0).count()
    pending_r = Operation.query.filter_by(operation_type='receipt', status='ready').count()
    pending_d = Operation.query.filter_by(operation_type='delivery', status='ready').count()

    # Most active product last 7 days
    from sqlalchemy import func
    top = db.session.query(
        Product.name,
        func.sum(StockLedger.quantity).label('vol')
    ).join(StockLedger, StockLedger.product_id == Product.id)\
     .filter(StockLedger.timestamp >= week_ago)\
     .group_by(Product.id)\
     .order_by(func.sum(StockLedger.quantity).desc())\
     .first()

    health = round(((total - low) / total * 100)) if total else 100

    insights = [
        f"📦 Stock health is at {health}% — {total - low} of {total} products are above reorder level.",
        f"⚠️ {low} product(s) are at or below reorder level{f', including {out} completely out of stock' if out else ''}. Immediate restocking recommended.",
        f"🚚 There are {pending_r} receipt(s) and {pending_d} delivery order(s) currently ready to process.",
        f"🔥 {'Top moving product this week: ' + top.name if top else 'No stock movements recorded this week — consider reviewing operations.'}",
    ]
    return insights

# ─────────────────────────────────────────
# START
# ─────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()       
        seed_sample_data()    
    print("StockSense running on http://localhost:5000")
    app.run(debug=True, port=5000)
