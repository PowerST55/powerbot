# Sistema de Sincronización de BD - PowerBot

## 📋 Descripción General

Sistema híbrido que mantiene **sincronización bidireccional** entre:
- **Cliente Local**: Caché JSON (`data/user_cache.json`)
- **VPS**: Base de datos MySQL (`panther.teramont.net`)

Esto asegura que ambos sistemas (cliente local + discordbot en VPS) tengan siempre los **datos más actualizados** sin duplicaciones ni desfases.

---

## 🚀 Inicialización Automática

El sistema se inicializa **automáticamente** cuando importas `usermanager.py`:

```python
from backend import usermanager

# Automáticamente:
# 1. Intenta conectar a BD MySQL
# 2. Crea las tablas si no existen
# 3. Inicializa SyncManager
# 4. El sistema funciona sin BD si falla (fallback a caché JSON)
```

---

## 🔄 Flujo de Sincronización

### Cuando agregues un usuario Discord:
```
1. cache_discord_user() → Crea/actualiza en caché JSON
2. sync_user_bidirectional() → Envía a BD MySQL
3. Ambos sistemas sincronizados ✓
```

### Cuando sumes/restes puntos:
```
1. add_points_to_user() → Actualiza en caché JSON
2. db_manager.add_points() → Sincroniza en BD
3. Transacciones registradas en ambos lados ✓
```

### Si la BD cae:
```
- Los cambios se guardan SOLO en caché JSON
- Cuando la BD vuelva online:
  → sync_tools.py fuerza resincronización automática
  → Todos los cambios se replican a BD
```

---

## 📊 Conflictos de Datos

### Resolución Automática (por timestamp):

```python
# Si hay diferencias entre caché y BD:
# - Gana la versión más RECIENTE
# - Si ambas tienen el mismo timestamp → Gana caché JSON (local)

Ejemplo:
  Caché JSON:  puntos=100 (actualizado hace 5 mins)
  BD MySQL:    puntos=90  (actualizado hace 10 mins)
  → Resultado: 100 (versión más reciente gana)
```

### Puntos Especiales:
```python
# Los puntos NO se sobrescriben, se FUSIONAN
# Se mantiene el MÁXIMO para evitar pérdidas

Ejemplo:
  Caché JSON:  puntos=100
  BD MySQL:    puntos=110
  → Resultado: 110 (máximo mantenido)
```

---

## 🛠️ Herramientas de Sincronización

### Script Interactivo: `sync_tools.py`

```bash
python Aislado/backend/sync_tools.py
```

**Opciones disponibles:**

1. **Sincronizar TODO a BD**
   - Sube todos los usuarios del caché a BD
   - Útil después de restaurar desde respaldo
   - Detecta y reemplaza duplicados

2. **Verificar Estado**
   - Compara: Usuarios en caché vs BD
   - Detecta desfases automáticamente
   - Avisa si hay diferencias

3. **Limpiar Duplicados**
   - Elimina usuarios duplicados en caché
   - Basado en YouTube ID y Discord ID
   - Mantiene la versión más completa

4. **Ver Conexión BD**
   - Muestra estado de conexión MySQL
   - Estadísticas: usuarios, transacciones, logs
   - Detalles del servidor

5. **Reconectar BD**
   - Intenta reconnectar si se cayó
   - Automático con reintentos
   - Fuerza reconexión manual

6. **Generar Reporte**
   - Usuarios totales por plataforma
   - Cuentas vinculadas
   - Top 5 usuarios por puntos
   - Total de puntos en circulación

---

## 📁 Estructura de Archivos

```
Aislado/backend/
├── database.py          ← Gestor de BD MySQL
├── sync_manager.py      ← Gestor de sincronización
├── usermanager.py       ← Funciones de usuario (modificado)
├── sync_tools.py        ← Script de utilidades
├── main.py              ← Punto de entrada
└── ...

Aislado/data/
├── user_cache.json      ← Respaldo de usuarios (caché principal)
└── backups/             ← Respaldos automáticos
    └── user_cache_backup_*.json
```

---

## 🔑 Variables de Entorno Requeridas

Archivo: `keys/.env`

```env
TOKEN=tu_token_discord
PREFIX=pw
DB_HOST=panther.teramont.net
DB_PORT=3306
DB_NAME=s4130_powerst
DB_USER=u4130_wkNOuSaty4
DB_PASSWORD=ng2pnrlgbu4+.4hPOb09erTj
```

---

## 📊 Tablas de BD MySQL

### `users`
- `id`: ID auto-incrementable
- `youtube_id`: ID único YouTube
- `discord_id`: ID único Discord
- `name`: Nombre del usuario
- `puntos`: Saldo de puntos
- `is_moderator`, `is_member`: Roles
- `platform_sources`: Array JSON de plataformas
- `synced_at`: Timestamp de última sincronización

### `transactions`
- Registra cada cambio de puntos
- Vinculado a usuarios
- Timestamp para auditoría

### `sync_log`
- Registra cada sincronización
- Previene duplicaciones
- Rastrea conflictos resueltos

---

## ⚠️ Casos de Uso Importantes

### Caso 1: BD Cae Temporalmente
```
→ Sistema sigue funcionando con caché JSON
→ Cambios se guardan localmente
→ Cuando BD vuelve → Resincronización automática
```

### Caso 2: VPS y Cliente Local Hacen Cambios Simultáneos
```
→ Ambos envían cambios a caché JSON
→ SyncManager fusiona automáticamente
→ Se mantienen los datos más recientes
→ Si hay conflictos en puntos → Se suma el máximo
```

### Caso 3: Restaurar desde Respaldo
```
→ restore_from_backup() en usermanager.py
→ Automáticamente fuerza sincronización a BD
→ force_sync_all_to_db() réplica todo a MySQL
```

### Caso 4: Duplicados Accidentales
```
→ cleanup_duplicates() detecta automáticamente
→ Elimina basado en YouTube ID + Discord ID
→ Mantiene la versión más completa
```

---

## 🔍 Monitoreo y Logs

El sistema genera logs detallados:

```python
# Ejemplo de salida:
✓ Conectado a BD MySQL 8.0.35: s4130_powerst
✓ Tablas verificadas/creadas exitosamente
✓ Usuario 'jhon' sincronizado a ambos sistemas
⚠ Desfase de puntos en 'maria': Local=100, BD=90
   → Manteniendo máximo: 100
✓ Sincronización completada: 42 exitosos, 0 errores
```

---

## 🚨 Troubleshooting

### "BD no conectada"
```bash
# Verificar credenciales en keys/.env
# Probar conexión manual:
mysql -h panther.teramont.net -u u4130_wkNOuSaty4 -p
```

### "Duplicados en caché"
```bash
# Ejecutar limpieza:
python Aislado/backend/sync_tools.py
# Opción 3: Limpiar duplicados
```

### "Desfase de datos"
```bash
# Forzar resincronización:
python Aislado/backend/sync_tools.py
# Opción 1: Sincronizar TODO a BD
# Opción 2: Verificar estado
```

### "Error al sincronizar usuario X"
```
→ Sistema continúa funcionando con caché JSON
→ Reintentará automáticamente cuando sea posible
→ Ver logs para detalles específicos del error
```

---

## 📈 Mejoras Futuras

- [ ] Sincronización en tiempo real (WebSocket)
- [ ] Backup automático a la nube
- [ ] Replicación maestro-maestro (HA)
- [ ] Caché distribuido (Redis)
- [ ] Métricas de sincronización
- [ ] Panel web de monitoreo

---

## 📞 Soporte

Si tienes problemas:
1. Ejecuta `sync_tools.py` para diagnosticar
2. Revisa los logs en el terminal
3. Verifica credenciales BD en `keys/.env`
4. Intenta `Opción 5: Reconectar BD`
5. Si persiste, restaura desde respaldo y resincroniza

---

**Última actualización:** 4 de febrero de 2026
