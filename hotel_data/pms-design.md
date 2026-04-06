A Property Management System (PMS) in the hotel context is a comprehensive
software platform that serves as the central hub for managing all aspects of
hotel operations. It's essentially the digital backbone that hotels use to run
their day-to-day business.

## Core Functions of a Hotel PMS:

Reservations & Front Desk Operations: • Room booking and availability management
• Guest check-in/check-out processes • Room assignments and upgrades • Guest
profile management

Revenue Management: • Rate management and pricing strategies • Occupancy
tracking and forecasting • Revenue reporting and analytics

Housekeeping & Maintenance: • Room status tracking (clean, dirty, out of order)
• Housekeeping task assignments • Maintenance request management

Guest Services: • Billing and payment processing • Guest communication and
preferences • Loyalty program management • Concierge services coordination

Reporting & Analytics: • Occupancy reports • Revenue analysis • Guest
satisfaction metrics • Operational performance data

## API Design

### Amazon API Gateway + AWS Lambda Functions

1. Availability & Pricing APIs (Prospecto)

GET /api/availability

- Query params: hotel_id, check_in, check_out, guests
- Returns: Available room types with pricing

GET /api/pricing

- Query params: hotel_id, room_type_id, check_in, check_out, package_type
- Returns: Detailed pricing breakdown

POST /api/quote

- Body: hotel_id, room_type_id, check_in, check_out, guests, package_type
- Returns: Quote with total pricing and terms

2. Booking APIs (Prospecto)

POST /api/reservations

- Body: guest_info, room_details, dates, package_type
- Returns: reservation_id and payment_required amount

POST /api/payment

- Body: reservation_id, payment_details (card info)
- Returns: payment confirmation and reservation status

3. Guest Services APIs (Huésped)

POST /api/checkout

- Body: room_number, guest_name, check_out_date
- Returns: checkout confirmation and any pending charges

POST /api/housekeeping-request

- Body: room_number, guest_name, request_type, description
- Returns: request_id and estimated completion time

## PostgreSQL Schema Design

### Core Tables

1. Hotels Table sql CREATE TABLE hotels ( hotel_id VARCHAR(50) PRIMARY KEY, name
   VARCHAR(200) NOT NULL, location VARCHAR(200) NOT NULL, timezone VARCHAR(50)
   DEFAULT 'America/Mexico_City', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

2. Room Types Table sql CREATE TABLE room_types ( room_type_id VARCHAR(50)
   PRIMARY KEY, hotel_id VARCHAR(50) NOT NULL REFERENCES hotels(hotel_id), name
   VARCHAR(100) NOT NULL, description TEXT, max_occupancy INTEGER NOT NULL,
   total_rooms INTEGER NOT NULL, base_rate DECIMAL(10,2) NOT NULL,
   breakfast_rate DECIMAL(10,2) NOT NULL, all_inclusive_rate DECIMAL(10,2) NOT
   NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP );

3. Rooms Table sql CREATE TABLE rooms ( room_id VARCHAR(50) PRIMARY KEY,
   hotel_id VARCHAR(50) NOT NULL REFERENCES hotels(hotel_id), room_number
   VARCHAR(20) NOT NULL, room_type_id VARCHAR(50) NOT NULL REFERENCES
   room_types(room_type_id), floor INTEGER, status VARCHAR(20) DEFAULT
   'available', -- available, maintenance, cleaning created_at TIMESTAMP DEFAULT
   CURRENT_TIMESTAMP, UNIQUE(hotel_id, room_number) );

4. Rate Modifiers Table (for dynamic pricing) sql CREATE TABLE rate_modifiers (
   modifier_id SERIAL PRIMARY KEY, hotel_id VARCHAR(50) NOT NULL REFERENCES
   hotels(hotel_id), room_type_id VARCHAR(50) REFERENCES
   room_types(room_type_id), -- NULL = applies to all room types start_date DATE
   NOT NULL, end_date DATE NOT NULL, multiplier DECIMAL(4,2) NOT NULL DEFAULT
   1.00, -- 1.5 = 50% increase, 0.8 = 20% discount reason VARCHAR(100), --
   'high_season', 'holiday', 'promotion' created_at TIMESTAMP DEFAULT
   CURRENT_TIMESTAMP );

5. Reservations Table sql CREATE TABLE reservations ( reservation_id VARCHAR(50)
   PRIMARY KEY, hotel_id VARCHAR(50) NOT NULL REFERENCES hotels(hotel_id),
   room_id VARCHAR(50) REFERENCES rooms(room_id), room_type_id VARCHAR(50) NOT
   NULL REFERENCES room_types(room_type_id), guest_name VARCHAR(200) NOT NULL,
   guest_email VARCHAR(200), guest_phone VARCHAR(50), check_in_date DATE NOT
   NULL, check_out_date DATE NOT NULL, guests INTEGER NOT NULL, package_type
   VARCHAR(20) NOT NULL, -- 'simple', 'breakfast', 'all_inclusive' nights
   INTEGER GENERATED ALWAYS AS (check_out_date - check_in_date) STORED,
   base_amount DECIMAL(10,2) NOT NULL, total_amount DECIMAL(10,2) NOT NULL,
   status VARCHAR(20) DEFAULT 'pending', -- pending, confirmed, checked_in,
   checked_out, cancelled payment_status VARCHAR(20) DEFAULT 'pending', --
   pending, paid, refunded created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP );

6. Housekeeping Requests Table sql CREATE TABLE housekeeping_requests (
   request_id VARCHAR(50) PRIMARY KEY, hotel_id VARCHAR(50) NOT NULL REFERENCES
   hotels(hotel_id), room_number VARCHAR(20) NOT NULL, guest_name VARCHAR(200)
   NOT NULL, request_type VARCHAR(50) NOT NULL, -- 'towels', 'pillows',
   'cleaning', 'amenities' description TEXT, priority VARCHAR(20) DEFAULT
   'normal', -- low, normal, high, urgent status VARCHAR(20) DEFAULT 'pending',
   -- pending, in_progress, completed, cancelled requested_at TIMESTAMP DEFAULT
   CURRENT_TIMESTAMP, completed_at TIMESTAMP, notes TEXT );

### Indexes for Performance

sql -- Reservations indexes CREATE INDEX idx_reservations_hotel_dates ON
reservations(hotel_id, check_in_date, check_out_date); CREATE INDEX
idx_reservations_room_dates ON reservations(room_id, check_in_date,
check_out_date); CREATE INDEX idx_reservations_status ON reservations(status);

-- Housekeeping indexes  
CREATE INDEX idx_housekeeping_hotel_status ON housekeeping_requests(hotel_id,
status); CREATE INDEX idx_housekeeping_room ON housekeeping_requests(hotel_id,
room_number);

-- Rate modifiers indexes CREATE INDEX idx_rate_modifiers_dates ON
rate_modifiers(hotel_id, start_date, end_date);

## API Design with SQL Queries

### 1. Availability Check

sql -- Get available room types for date range WITH occupied_rooms AS ( SELECT
room_type_id, COUNT(_) as reserved_count FROM reservations WHERE hotel_id = $1
AND status IN ('confirmed', 'checked_in') AND check_in_date < $3 --
check_out_date parameter AND check_out_date > $2 -- check_in_date parameter
GROUP BY room_type_id ), pricing AS ( SELECT rt.room_type_id, CASE WHEN $4 =
'simple' THEN rt.base_rate WHEN $4 = 'breakfast' THEN rt.breakfast_rate  
 WHEN $4 = 'all_inclusive' THEN rt.all_inclusive_rate END _
COALESCE(rm.multiplier, 1.0) as rate_per_night FROM room_types rt LEFT JOIN
rate_modifiers rm ON rt.room_type_id = rm.room_type_id AND $2 BETWEEN
rm.start_date AND rm.end_date -- check_in_date WHERE rt.hotel_id = $1 ) SELECT
rt.room_type_id, rt.name, rt.max_occupancy, rt.total_rooms, rt.total_rooms -
COALESCE(or.reserved_count, 0) as available_rooms, p.rate_per_night,
p.rate_per_night \* ($3::date - $2::date) as total_cost FROM room_types rt LEFT
JOIN occupied_rooms or ON rt.room_type_id = or.room_type_id  
LEFT JOIN pricing p ON rt.room_type_id = p.room_type_id WHERE rt.hotel_id = $1
AND rt.max_occupancy >= $5 -- guest_count parameter AND rt.total_rooms >
COALESCE(or.reserved_count, 0);

### 2. Create Reservation

sql -- First, assign an available room WITH available_room AS ( SELECT r.room_id
FROM rooms r WHERE r.hotel_id = $1 AND r.room_type_id = $2 AND r.status =
'available' AND r.room_id NOT IN ( SELECT room_id FROM reservations WHERE
room_id IS NOT NULL AND status IN ('confirmed', 'checked_in') AND check_in_date
< $4 -- check_out_date AND check_out_date > $3 -- check_in_date ) LIMIT 1 )
INSERT INTO reservations ( reservation_id, hotel_id, room_id, room_type_id,
guest_name, guest_email, check_in_date, check_out_date, guests, package_type,
base_amount, total_amount ) SELECT $5, $1, ar.room_id, $2, $6, $7, $3, $4, $8,
$9, $10, $11 FROM available_room ar RETURNING reservation_id, room_id;

### 3. Checkout Process

sql -- Simple checkout - just update status UPDATE reservations SET status =
'checked_out', updated_at = CURRENT_TIMESTAMP WHERE hotel_id = $1 AND guest_name
ILIKE $2 AND room_id = ( SELECT room_id FROM rooms WHERE hotel_id = $1 AND
room_number = $3 ) AND status = 'checked_in' AND check_out_date >= $4::date --
checkout_date RETURNING reservation_id, total_amount, guest_name;

### 4. Housekeeping Request

sql INSERT INTO housekeeping_requests ( request_id, hotel_id, room_number,
guest_name, request_type, description, priority ) VALUES ( $1, $2, $3, $4, $5,
$6, CASE WHEN $5 = 'cleaning' THEN 'high' ELSE 'normal' END ) RETURNING
request_id, requested_at;
