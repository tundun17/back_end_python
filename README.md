# Smart Home Backend Django MQTT

Backend cho he thong nha thong minh su dung Django REST Framework lam REST API server va MQTT de giao tiep voi ESP32. Dashboard, Swagger hoac Postman goi API den Django; ESP32 gui/nhan du lieu qua MQTT broker.

## Muc tieu

- Quan ly user, nha, phong, ESP va switch.
- Nhan du lieu cam bien nhiet do, do am, khoi qua MQTT.
- Dieu khien switch/relay tu REST API bang cach publish MQTT command.
- Dong bo trang thai thuc te cua switch khi ESP publish state.
- Luu lich su command, canh bao, MQTT message va activity log de de kiem thu va bao cao.

## Kien truc

```text
Dashboard / Postman / Swagger
        |
        | REST API + JWT
        v
Django REST Framework Backend
        |
        | Django ORM
        v
SQLite / MySQL / PostgreSQL

Django MQTT Worker <----> HiveMQ / MQTT Broker <----> ESP32
```

## MQTT topics

```text
syn                  ESP -> Django: bao online
{hashcode}/ack       Django -> ESP: xac nhan ESP da duoc chap nhan
{hashcode}/sensor    ESP -> Django: gui du lieu cam bien
{hashcode}/state     ESP -> Django: gui trang thai switch thuc te
{hashcode}/set       Django -> ESP: gui lenh bat/tat switch
```

Payload `syn`:

```json
{
  "hashcode": "ESP_ABC123",
  "ip_address": "192.168.1.50",
  "firmware_version": "1.0.0",
  "is_sensor": false,
  "num_switches": 2
}
```

Payload ACK sau khi backend xu ly `syn` thanh cong:

```json
{
  "hashcode": "ESP_ABC123",
  "ack": "OK"
}
```

Payload sensor:

```json
{
  "temperature": 31.5,
  "humidity": 72.0,
  "gas": 420
}
```

Payload command:

```json
{
  "command_id": 25,
  "command_type": "SET_DEVICE_STATE",
  "switch_code": "SWITCH_01",
  "state": "ON"
}
```

Payload state:

```json
{
  "command_id": 25,
  "switch_code": "SWITCH_01",
  "actual_state": "ON",
}
```

Voi cong tac vat ly, ESP co the gui state khong co `command_id`; backend van cap nhat `Switch.actual_state` va `Switch.sync_status`.

## Database chinh

- `Home`: nha cua user.
- `Room`: phong trong tung nha.
- `ESP`: ESP32, hashcode, phong, trang thai online/offline.
- `Switch`: switch/relay gan voi ESP, trang thai mong muon va trang thai thuc te.
- `SensorReading`: du lieu nhiet do, do am, muc khoi.
- `DeviceCommand`: lich su lenh backend publish xuong ESP.
- `Alert`: canh bao sensor hoac thiet bi.
- `MQTTMessage`: log MQTT inbound/outbound.
- `ActivityLog`: lich su thao tac user/he thong.

## REST API du kien

### Auth va user

```text
POST  /api/auth/register/
POST  /api/auth/login/
POST  /api/auth/refresh/
GET   /api/users/me/
PATCH /api/users/me/
POST  /api/users/change-password/
```

### Home va room

```text
GET    /api/homes/
POST   /api/homes/
GET    /api/homes/{id}/
PATCH  /api/homes/{id}/
DELETE /api/homes/{id}/
GET    /api/homes/{home_id}/rooms/
POST   /api/homes/{home_id}/rooms/
PATCH  /api/rooms/{id}/
DELETE /api/rooms/{id}/
```

### ESP

```text
GET    /api/esps/
POST   /api/esps/
GET    /api/esps/{hashcode}/
PATCH  /api/esps/{hashcode}/
DELETE /api/esps/{hashcode}/
GET    /api/esps/{hashcode}/mqtt-messages/
```

### Switch va dieu khien

```text
GET    /api/esps/{hashcode}/switches/
GET    /api/esps/{hashcode}/switches/{switch_code}/
PATCH  /api/esps/{hashcode}/switches/{switch_code}/
POST   /api/esps/{hashcode}/switches/{switch_code}/control/
GET    /api/esps/{hashcode}/switches/{switch_code}/commands/
```

Payload control switch:

```json
{
  "state": "ON"
}
```

`state` chap nhan: `ON`, `OFF`, `1`, `0`, `true`, `false`.

### Sensor, alert va dashboard

```text
GET   /api/esps/{hashcode}/sensor-readings/latest/
GET   /api/esps/{hashcode}/sensor-readings/history/
GET   /api/sensor-readings/
GET   /api/alerts/
GET   /api/alerts/{id}/
PATCH /api/alerts/{id}/resolve/
GET   /api/dashboard/overview/
GET   /api/dashboard/homes/{id}/overview/
GET   /api/dashboard/homes/{id}/analytics/
```

### Debug MQTT

```text
GET  /api/mqtt/messages/
GET  /api/mqtt/messages/{id}/
POST /api/mqtt/test-publish/
POST /api/debug/mqtt/inbound/
```

## Chay project

Chay migration:

```bash
python manage.py migrate
```

Chay REST API server:

```bash
python manage.py runserver
```

Chay MQTT worker o terminal khac:

```bash
python manage.py mqtt_worker
```

Kiem tra ESP offline:

```bash
python manage.py health_check
```

Neu ESP dang `ONLINE` nhung qua 10 phut khong gui MQTT len backend, command nay se chuyen ESP do sang `OFFLINE`.

## Cau hinh MQTT

Tao file `.env` tai thu muc project:

```text
MQTT_BROKER="your-hivemq-host"
MQTT_PORT=8883
MQTT_USERNAME="your-username"
MQTT_PASSWORD="your-password"
MQTT_TLS=True
MQTT_KEEPALIVE=60
MQTT_QOS=0
SMOKE_THRESHOLD=800
TEMPERATURE_THRESHOLD=45
ESP_OFFLINE_TIMEOUT_MINUTES=10
```

## Kiem thu khong can ESP

1. Tao `ESP` va `Switch` trong Django Admin.
2. Chay:

```bash
python manage.py mqtt_worker
```

3. Publish bang HiveMQ Web Client hoac MQTTX.

Topic:

```text
syn
```

Payload:

```json
{
  "hashcode": "ESP_ABC123",
  "ip_address": "192.168.1.50",
  "firmware_version": "1.0.0",
  "is_sensor": false,
  "num_switches": 2
}
```

Topic:

```text
ESP_ABC123/sensor
```

Payload:

```json
{
  "temperature": 50,
  "humidity": 70,
  "gas": 900
}
```

Topic:

```text
ESP_ABC123/state
```

Payload:

```json
{
  "switch_code": "SWITCH_01",
  "actual_state": "ON",
  "success": true
}
```

Ket qua mong muon:

- `ESP.status = ONLINE`
- Tao `SensorReading`
- Tao `Alert` neu vuot nguong
- `Switch.actual_state = ON`
- Co log trong `MQTTMessage`

## Chuc nang noi bat

Chuc nang trong tam cua do an la dieu khien switch thong qua REST API ket hop MQTT state sync. Khi user bat/tat switch, backend tao command, publish MQTT xuong ESP, ghi log message va doi ESP publish state nguoc lai. Khi nhan state, MQTT worker cap nhat trang thai thuc te cua switch va trang thai command. Chuc nang nay the hien ro backend logic, database design, MQTT integration va kha nang kiem thu he thong.
