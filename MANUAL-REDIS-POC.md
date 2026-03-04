# Manual de Instalación y Prueba de Concepto de Redis

Guía completa para instalar Redis en máquina virtual o contenedor, realizar pruebas de concepto (PoC) de sus casos de uso (cache, base de datos vectorial, etc.) y realizar el dimensionamiento adecuado.

---

## Tabla de Contenidos

1. [Pre-requisitos](#1-pre-requisitos)
2. [Sizing y Dimensionamiento](#2-sizing-y-dimensionamiento)
3. [Instalación en Máquina Virtual](#3-instalación-en-máquina-virtual)
4. [Despliegue en Contenedor Docker](#4-despliegue-en-contenedor-docker)
5. [Casos de Uso para PoC](#5-casos-de-uso-para-poc)
6. [Verificación y Pruebas](#6-verificación-y-pruebas)

---

## 1. Pre-requisitos

### 1.1 Sistema Operativo

| Entorno | Sistemas Soportados |
|---------|---------------------|
| **Linux** | Ubuntu 20.04/22.04/24.04, Debian 10/11/12, RHEL 8/9, Rocky Linux, Amazon Linux 2023 |
| **Contenedor** | Cualquier host con Docker 20.10+ o Podman |

### 1.2 Recursos Mínimos Recomendados

| Escenario | CPU | RAM | Storage | Notas |
|-----------|-----|-----|---------|-------|
| **PoC / Desarrollo** | 2 cores | 2-4 GB | 10-20 GB | Suficiente para pruebas básicas |
| **PoC con Redis Stack** | 2-4 cores | 4-8 GB | 20-50 GB | Incluye vectores, búsqueda, JSON |
| **Producción ligera** | 4 cores | 8-16 GB | 50-100 GB | Con replicación básica |
| **Producción media** | 8+ cores | 16-32 GB | 100-500 GB | Alta disponibilidad |

### 1.3 Requisitos Software

- **Docker** (para contenedores): Docker Engine 20.10+ o Docker Desktop 4.37+
- **Linux VM**: Usuario con privilegios `sudo`, paquetes `curl`, `gnupg`, `lsb-release`
- **Red**: Puerto 6379 (Redis) disponible; puerto 8001 si usas Redis Stack con Redis Insight

---

## 2. Sizing y Dimensionamiento

### 2.1 Cálculo de Memoria

**Regla general:** Asignar 50-75% de la RAM del sistema como `maxmemory` de Redis, dejando espacio para el sistema operativo y operaciones.

```
maxmemory = (RAM_total × 0.65) 
```

**Consideraciones adicionales:**

| Factor | Multiplicador | Descripción |
|--------|---------------|-------------|
| **Replicación** | ×2 | Con réplica, duplica el consumo (512 MB datos → 1 GB total) |
| **Active-Active** | ×4 | En configuración multi-master puede cuadruplicar |
| **Módulos (Stack)** | +30-50% | Redis Stack, índices de búsqueda y vectores consumen más |
| **Overhead Redis** | +10% | Estructuras internas y fragmentación |

**Ejemplo para PoC:**
- VM con 8 GB RAM → `maxmemory` sugerido: 4-5 GB
- Datos estimados: 2 GB → Memoria total necesaria: ~4 GB (con margen)

### 2.2 Storage

| Tipo de persistencia | Fórmula | Ejemplo |
|---------------------|---------|---------|
| **RDB (snapshots)** | 1-1.5× tamaño del dataset en memoria | 4 GB RAM → 4-6 GB disk |
| **AOF** | 1.5-2× tamaño del dataset | 4 GB RAM → 6-8 GB disk |
| **RDB + AOF** | 2-3× tamaño del dataset | 4 GB RAM → 8-12 GB disk |

**Recomendación para PoC:** 2-3× el tamaño estimado del dataset; mínimo 20 GB para logs y snapshots.

### 2.3 CPU

- Un núcleo maneja ~100,000 RPS para comandos simples (GET, SET)
- Operaciones complejas (HGETALL, búsquedas, vectores) son 50-100× más costosas
- Para PoC: 2 cores suficientes; para vectores/búsquedas: 4 cores recomendados

---

## 3. Instalación en Máquina Virtual

### 3.1 Ubuntu / Debian (Repositorio Oficial)

```bash
# Instalar dependencias
sudo apt-get update
sudo apt-get install -y lsb-release curl gpg

# Añadir repositorio oficial de Redis
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
sudo chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list

# Instalar Redis
sudo apt-get update
sudo apt-get install -y redis

# Habilitar e iniciar el servicio
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### 3.2 Red Hat / RHEL / Rocky Linux / AlmaLinux (RPM)

En Red Hat Enterprise Linux (RHEL) 8/9, Rocky Linux y AlmaLinux puedes usar el repositorio oficial de Redis o los paquetes de la distribución.

**Opción A: Repositorio oficial de Redis (recomendado, versión reciente)**

```bash
# Importar la clave GPG de Redis
curl -fsSL https://packages.redis.io/gpg > /tmp/redis.key
sudo rpm --import /tmp/redis.key

# Crear el repositorio (elegir según versión)
# Para RHEL 9 / Rocky Linux 9 / AlmaLinux 9:
sudo tee /etc/yum.repos.d/redis.repo << 'EOF'
[Redis]
name=Redis
baseurl=https://packages.redis.io/rpm/rockylinux9
enabled=1
gpgcheck=1
EOF

# Para RHEL 8 / Rocky Linux 8 / AlmaLinux 8:
# baseurl=https://packages.redis.io/rpm/rockylinux8

# Instalar Redis
sudo dnf install -y redis
# o: sudo yum install -y redis

# Habilitar e iniciar el servicio (en RHEL el servicio se llama redis)
sudo systemctl enable redis
sudo systemctl start redis
```

**Opción B: Paquetes de la distribución (dnf/yum)**

```bash
sudo dnf install -y redis
# o: sudo yum install -y redis

sudo systemctl enable redis
sudo systemctl start redis
```

**Firewall (si necesitas acceso remoto):**

```bash
sudo firewall-cmd --zone=public --permanent --add-port=6379/tcp
# o por servicio, si está definido:
# sudo firewall-cmd --zone=public --permanent --add-service=redis
sudo firewall-cmd --reload
```

**Nota:** En RHEL/Rocky/AlmaLinux el servicio es `redis` (no `redis-server`) y el archivo de configuración suele estar en `/etc/redis.conf`.

### 3.3 Configuración Básica de Sizing

Editar `/etc/redis/redis.conf` (Debian/Ubuntu) o `/etc/redis.conf` (Red Hat):

```conf
# Memoria máxima (ejemplo: 4GB)
maxmemory 4gb

# Política de evicción para cache
maxmemory-policy allkeys-lru

# Persistencia RDB
save 60 1
save 300 10
save 3600 10000

# Persistencia AOF (opcional, más durable)
appendonly yes
appendfsync everysec
```

Reiniciar el servicio:

```bash
# Debian/Ubuntu
sudo systemctl restart redis-server

# Red Hat / RHEL / Rocky / AlmaLinux
sudo systemctl restart redis
```

### 3.4 Verificación

```bash
redis-cli ping
# Respuesta esperada: PONG

redis-cli info memory
# Muestra uso de memoria
```

---

## 4. Despliegue en Contenedor Docker

### 4.1 Imagen Oficial de Redis (Cache / Base de Datos Simple)

La imagen oficial `redis` en Docker Hub es mantenida por Redis LTD y es la más utilizada:

- **Imagen:** `redis:latest` (actualmente 8.6.x)
- **Variantes:** `redis:alpine` (más ligera), `redis:8.4`, `redis:7.4` para versiones específicas

**Despliegue básico:**

```bash
docker run -d --name redis-poc -p 6379:6379 redis:latest
```

**Con persistencia y sizing:**

```bash
docker run -d \
  --name redis-poc \
  -p 6379:6379 \
  -v $(pwd)/redis-data:/data \
  --memory=4g \
  redis:latest redis-server \
    --save 60 1 \
    --maxmemory 3gb \
    --maxmemory-policy allkeys-lru
```

**Con configuración personalizada:**

```bash
# Crear directorio y archivo redis.conf
mkdir -p ./redis-conf
# Editar redis.conf según necesidades de sizing

docker run -d \
  --name redis-poc \
  -p 6379:6379 \
  -v $(pwd)/redis-data:/data \
  -v $(pwd)/redis-conf/redis.conf:/usr/local/etc/redis/redis.conf \
  redis:latest redis-server /usr/local/etc/redis/redis.conf
```

### 4.2 Imagen Redis Stack (Cache + Vectores + Búsqueda + JSON)

Para PoC con **base de datos vectorial**, búsqueda full-text y JSON, usa Redis Stack:

| Imagen | Uso | Puertos |
|--------|-----|---------|
| `redis/redis-stack-server:latest` | Producción / servidor solo | 6379 |
| `redis/redis-stack:latest` | Desarrollo (incluye Redis Insight UI) | 6379, 8001 |

**Despliegue para PoC con vectores:**

```bash
# Servidor solo (producción / PoC headless)
docker run -d \
  --name redis-stack-poc \
  -p 6379:6379 \
  -v $(pwd)/redis-stack-data:/data \
  --memory=6g \
  redis/redis-stack-server:latest
```

**Con Redis Insight (interfaz gráfica para explorar datos):**

```bash
docker run -d \
  --name redis-stack-poc \
  -p 6379:6379 \
  -p 8001:8001 \
  -v $(pwd)/redis-stack-data:/data \
  --memory=6g \
  redis/redis-stack:latest
```

Acceso a Redis Insight: `http://localhost:8001`

**Con persistencia y límites de memoria:**

```bash
docker run -d \
  --name redis-stack-poc \
  -p 6379:6379 \
  -p 8001:8001 \
  -v $(pwd)/redis-stack-data:/data \
  -e REDIS_ARGS="--save 60 1000 --appendonly yes --maxmemory 4gb --maxmemory-policy allkeys-lru" \
  redis/redis-stack:latest
```

### 4.3 Docker Compose (Recomendado para PoC)

Crear `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis-poc:
    image: redis:latest
    container_name: redis-poc
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --save 60 1 --maxmemory 3gb --maxmemory-policy allkeys-lru
    deploy:
      resources:
        limits:
          memory: 4G

  redis-stack-poc:
    image: redis/redis-stack:latest
    container_name: redis-stack-poc
    ports:
      - "6380:6379"
      - "8001:8001"
    volumes:
      - redis-stack-data:/data
    environment:
      - REDIS_ARGS=--save 60 1000 --appendonly yes --maxmemory 4gb
    deploy:
      resources:
        limits:
          memory: 6G
    profiles:
      - stack

volumes:
  redis-data:
  redis-stack-data:
```

Ejecutar:

```bash
# Solo Redis básico
docker compose up -d

# Redis Stack (vectores, búsqueda, JSON)
docker compose --profile stack up -d
```

---

## 5. Casos de Uso para PoC

### 5.1 Cache de Sesiones / Objetos

**Imagen:** `redis:latest`

```bash
# Conectar
redis-cli

# Ejemplo básico
SET usuario:1001 '{"nombre":"Juan","rol":"admin"}'
GET usuario:1001

# Con TTL (segundos)
SET sesion:abc123 "datos" EX 3600
TTL sesion:abc123
```

### 5.2 Base de Datos de Vectores (Embeddings, RAG)

**Imagen:** `redis/redis-stack-server:latest` o `redis/redis-stack:latest`

Requiere RediSearch con soporte vectorial. Ejemplo con Redis Stack:

```bash
# Crear índice vectorial (vía redis-cli o cliente)
FT.CREATE idx:docs ON HASH PREFIX 1 doc: SCHEMA 
  contenido TEXT 
  embedding VECTOR HNSW 6 DIM 1536 DISTANCE_METRIC COSINE
```

Luego realizar búsquedas por similitud (KNN).

### 5.3 Búsqueda Full-Text y JSON

**Imagen:** Redis Stack

```bash
# Crear índice en campos JSON
FT.CREATE idx:productos ON JSON PREFIX 1 prod: SCHEMA 
  $.nombre TEXT 
  $.categoria TAG 
  $.precio NUMERIC
```

### 5.4 Time Series (Métricas, IoT)

**Imagen:** Redis Stack (incluye RedisTimeSeries)

```bash
# Crear serie temporal
TS.CREATE sensor:temp
TS.ADD sensor:temp 1709308800000 23.5
TS.RANGE sensor:temp 1709308800000 1709395200000
```

### 5.5 Estructuras Probabilísticas (Bloom, Count-Min Sketch)

**Imagen:** Redis Stack (incluye RedisBloom)

```bash
BF.ADD filtro:emails "user@example.com"
BF.EXISTS filtro:emails "user@example.com"
```

### 5.6 Change Data Collector (Oracle → Redis)

Sincronización incremental de un catálogo desde Oracle a Redis cada 30 segundos, actualizando **solo los registros que cambiaron** para no sobrecargar ni la base ni Redis.

#### Origen de los datos: tablas o vistas

Hay que definir **de dónde se lee** la información y **cómo se identifica** cada registro:

| Origen | Descripción | Consideraciones |
|--------|-------------|-----------------|
| **Una sola tabla** | `SELECT * FROM MI_CATALOGO WHERE UPDATED_AT > :last_sync` | La PK (ej. `ID`) define la clave en Redis. La tabla debe tener columna de auditoría (ej. `UPDATED_AT`). |
| **Una vista** | `SELECT * FROM V_MI_CATALOGO WHERE ...` | La vista debe exponer una columna tipo “clave” (única por fila) y, si se quiere CDC incremental, una columna de fecha de modificación. Si la vista no tiene auditoría, se puede hacer carga completa cada vez (menos eficiente). |
| **Varias tablas o vistas** | Varias consultas, cada una con su propia clave y opcionalmente su `last_sync` | Un script por fuente (o un mismo script con configuración por fuente). En Redis se distinguen con distinto prefijo, ej. `catalog:TablaA:ID`, `catalog:VistaB:CODIGO`. |
| **JOIN de varias tablas** | Una vista o una consulta SQL que hace JOIN | Se trata como **una sola fuente**: una fila resultante = un documento en Redis. La “clave única” debe ser una columna (o concatenación) que identifique cada fila (ej. `ID` de la tabla maestra). |

**Recomendación:** Para CDC incremental, que al menos una tabla base tenga columna de auditoría (`UPDATED_AT` / `MODIFIED_DATE`) actualizada por trigger o por la aplicación. Si solo hay vistas sin auditoría, usar carga completa en cada ciclo.

#### Transformación para Redis (diferencias de tipo de dato)

Redis guarda **strings** (o estructuras como hash/list). Si guardamos un “documento” por registro, lo normal es serializarlo en **JSON**. Oracle tiene tipos que JSON no tiene; hay que **transformar** antes de guardar:

| Tipo Oracle | En Redis/JSON | Transformación recomendada |
|-------------|---------------|----------------------------|
| `NUMBER`, `INTEGER` | Número o string | Mantener como número en JSON si es entero/decimal “simple”; si puede ser muy grande o precisión crítica, guardar como string para evitar pérdida. |
| `VARCHAR2`, `CHAR`, `CLOB` | String | Directo. CLOB muy grandes: considerar truncar o comprimir si no se necesitan completos en Redis. |
| `DATE`, `TIMESTAMP` | String ISO 8601 | Convertir a `YYYY-MM-DDTHH:MM:SS.ffffff` (o sin fracción) para orden y compatibilidad. |
| `TIMESTAMP WITH TIME ZONE` | String ISO con zona | Incluir zona (ej. `Z` o `+00:00`) para no perder información. |
| `BLOB`, `RAW` | No estándar en JSON | Evitar en cache de catálogo; si hace falta, guardar como Base64 (string) o referenciar por ID y no sincronizar el contenido. |
| `NULL` | `null` en JSON | No guardar string vacío; usar `null` para que el consumidor distinga “no definido”. |
| `FLOAT`, `BINARY_FLOAT/DOUBLE` | Número | Directo; vigilar NaN/Infinity (no válidos en JSON estándar, convertirlos a `null` o string). |

**Reglas prácticas:**

1. **Un registro = un valor en Redis:** clave `prefix:origen:id` (ej. `catalog:MI_CATALOGO:123`), valor = JSON del registro ya transformado.
2. **Fechas siempre como string** en JSON (ISO) para evitar diferencias de zona y de precisión entre lenguajes.
3. **Nulos:** dejar como `null` en JSON; en el script no mapear `NULL` de Oracle a `""` si quieres distinguir “no definido”.
4. **Números muy grandes o precisión exacta:** serializar como string para que no se redondee en JSON.
5. **Varias fuentes:** cada una con su prefijo y, si aplica, su propia `last_sync` en Redis (ej. `catalog:Tabla1:last_sync`, `catalog:Vista2:last_sync`).

Con esto se entiende **cómo se saca** la información (una o varias tablas/vistas, una o varias consultas) y **cómo se transforma** para guardarla en Redis sin problemas de tipo de dato.

**Requisitos en Oracle:** La tabla (o vista base) debe tener una columna de auditoría de modificación (por ejemplo `UPDATED_AT` tipo `TIMESTAMP`), actualizada por trigger o por la aplicación al hacer INSERT/UPDATE.

**Idea del script:** Consulta en Oracle las filas donde `UPDATED_AT > última_sincronización`, transforma cada fila (tipos Oracle → tipos JSON), serializa a JSON y guarda en Redis con clave `catalog:NombreTabla:ID`. La fecha de la última sincronización se guarda en Redis para la siguiente pasada.

**Script de ejemplo:** `scripts/oracle_redis_cdc.py` — aplica la transformación de tipos descrita arriba en la función `transform_value()` (fechas a ISO, `Decimal` a int/float, `NULL` a `null`, etc.).

Dependencias:

```bash
pip install oracledb redis
```

Variables de entorno (o editar el script):

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `ORACLE_DSN` | Conexión Oracle (host:puerto/servicio) | `localhost:1521/ORCLPDB1` |
| `ORACLE_USER` / `ORACLE_PASSWORD` | Usuario Oracle | — |
| `ORACLE_TABLE` | Nombre de la tabla catálogo | `MI_CATALOGO` |
| `ORACLE_KEY_COLUMN` | Columna que identifica el registro (PK) | `ID` |
| `ORACLE_CHANGE_COLUMN` | Columna de fecha de última modificación | `UPDATED_AT` |
| `REDIS_HOST` / `REDIS_PORT` | Redis | `localhost`, `6379` |
| `REDIS_PREFIX` | Prefijo de claves en Redis | `catalog` |
| `CDC_INTERVAL_SECONDS` | Intervalo entre sincronizaciones (segundos) | `30` |

Ejecución:

```bash
cd scripts
export ORACLE_PASSWORD="tu_password"
python oracle_redis_cdc.py
```

El script corre en bucle; cada 30 segundos consulta Oracle por filas con `UPDATED_AT > last_sync` y actualiza solo esas claves en Redis.

---

## 6. Verificación y Pruebas

### 6.1 Comprobar Conectividad

```bash
# Si Redis está en Docker
docker exec -it redis-poc redis-cli ping

# Si Redis está en VM
redis-cli -h localhost -p 6379 ping
```

### 6.2 Monitoreo de Memoria y Rendimiento

```bash
redis-cli info memory
redis-cli info stats
redis-cli --latency
redis-cli --bigkeys
```

### 6.3 Benchmark Rápido

```bash
redis-benchmark -h localhost -p 6379 -c 50 -n 10000 -q
```

---

## Resumen de Imágenes Docker Recomendadas

| Caso de Uso | Imagen | Comando de Ejecución Rápida |
|-------------|--------|-----------------------------|
| Cache / DB simple | `redis:latest` | `docker run -d -p 6379:6379 redis:latest` |
| Vectores + Búsqueda + JSON | `redis/redis-stack:latest` | `docker run -d -p 6379:6379 -p 8001:8001 redis/redis-stack:latest` |
| Producción (solo servidor) | `redis/redis-stack-server:latest` | `docker run -d -p 6379:6379 redis/redis-stack-server:latest` |

---

## Referencias

- [Redis Official Docker Image](https://hub.docker.com/_/redis)
- [Redis Stack on Docker](https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-stack/docker/)
- [Redis Sizing Best Practices](https://redis.io/docs/latest/operate/rc/databases/configuration/sizing/)
- [Redis Persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
