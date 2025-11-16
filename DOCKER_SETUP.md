# Docker Setup for End-to-End Testing

## 🚀 Quick Start

### Step 1: Create Your `.env` File

Copy the example and fill in your real credentials:

```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

**Required Settings:**
- `MAM_SERVICE_API_KEY` - Any string you want (will use in AudioBookRequest)
- `MAM_SERVICE_MAM_SESSION_ID` - Your MAM session cookie
- `MAM_SERVICE_TRANSMISSION_URL` - Your seedbox Transmission RPC URL
- `MAM_SERVICE_TRANSMISSION_USERNAME` - Transmission username
- `MAM_SERVICE_TRANSMISSION_PASSWORD` - Transmission password

**Set Mock Mode to False:**
```bash
MAM_SERVICE_USE_MOCK_DATA=false
```

### Step 2: Build and Start Containers

```bash
# Build the image (first time or after code changes)
docker-compose build

# Start the containers
docker-compose up -d

# View logs
docker-compose logs -f
```

### Step 3: Access the Services

- **AudioBookRequest**: http://localhost:8000
- **Mamlarr**: http://localhost:8800/mamlarr/

### Step 4: Configure Mamlarr Settings

Option A: Via UI (Recommended)
1. Go to http://localhost:8800/mamlarr/settings
2. Enter your MAM session cookie
3. Enter Transmission RPC details
4. Click "Test Connection" to verify
5. Save settings

Option B: Via Environment Variables (already done in .env)

### Step 5: Configure AudioBookRequest to Use Mamlarr

1. Go to AudioBookRequest settings (http://localhost:8000)
2. Configure Prowlarr integration:
   - **Prowlarr URL**: `http://localhost:8800`
   - **API Key**: (same as `MAM_SERVICE_API_KEY` from .env)
3. Test connection - should see "MyAnonamouse" indexer

### Step 6: Test End-to-End

1. Search for an audiobook in AudioBookRequest
2. Click download
3. Watch the Mamlarr dashboard: http://localhost:8800/mamlarr/
4. Monitor job progress:
   - Download → Seeding → Processing → Complete
5. Check downloads folder: `./downloads/`

## 📊 Monitoring

### View Logs
```bash
# All logs
docker-compose logs -f

# Just mamlarr
docker-compose logs -f abr-mamlarr | grep mamlarr

# Just errors
docker-compose logs -f | grep -i error
```

### Check Status
```bash
# Container status
docker-compose ps

# Health check
curl http://localhost:8800/health
```

### Restart Services
```bash
# Restart everything
docker-compose restart

# Rebuild after code changes
docker-compose down
docker-compose build
docker-compose up -d
```

## 🔍 Getting Your MAM Session Cookie

### Method 1: Browser DevTools
1. Go to https://www.myanonamouse.net
2. Log in
3. Press F12 (open DevTools)
4. Go to **Application** → **Cookies** → `https://www.myanonamouse.net`
5. Find `mam_id` cookie
6. Copy the **Value**
7. Paste into `.env` file as `MAM_SERVICE_MAM_SESSION_ID`

### Method 2: Chrome Network Tab
1. Go to MyAnonamouse
2. Open DevTools (F12) → **Network** tab
3. Refresh the page
4. Click any request
5. Look at **Request Headers** → **Cookie**
6. Find `mam_id=...` and copy the value

### Method 3: Firefox Storage Inspector
1. Go to MyAnonamouse
2. Press F12 → **Storage** tab
3. Expand **Cookies** → `https://www.myanonamouse.net`
4. Find `mam_id` row
5. Copy the **Value** column

## 🛠️ Troubleshooting

### Connection Refused to Transmission
- Check Transmission RPC URL format: `http://host:9091/transmission/rpc`
- Verify credentials are correct
- Ensure seedbox is accessible from your network
- Try pinging the seedbox host

### MAM Session Invalid
- Cookie may have expired - get a fresh one
- Make sure you copied the entire cookie value
- Check if you're logged into MAM in browser

### Downloads Not Starting
- Check logs: `docker-compose logs -f`
- Verify Transmission connection in settings UI
- Test Transmission RPC manually:
  ```bash
  curl -u "user:pass" http://your-seedbox:9091/transmission/rpc
  ```

### Audio Processing Failing
- ffmpeg is now installed in the container (if you rebuilt)
- Check logs for ffmpeg errors
- Verify downloaded files are valid audio formats

### Settings Not Persisting
- Check `./data/settings.json` exists
- Volume is mounted: `./data:/srv/mamlarr/data`
- Container has write permissions

## 📁 Volume Mounts

The docker-compose.yml mounts two directories:

1. **`./data`** → `/srv/mamlarr/data`
   - Settings persistence (`settings.json`)
   - Database (if added later)

2. **`./downloads`** → `/downloads`
   - Processed audiobooks
   - Metadata files

Both persist after container restarts.

## 🔄 Updating

### Code Changes
```bash
git pull origin master
docker-compose build
docker-compose up -d
```

### Environment Variables
```bash
# Edit .env file
nano .env

# Restart to apply
docker-compose restart
```

### AudioBookRequest Updates
The Dockerfile clones from `Brownster/audiobookrequest` on build.
To update:
```bash
docker-compose build --no-cache
docker-compose up -d
```

## 🎯 Expected Behavior

### Successful Flow:
1. Search in AudioBookRequest → Results from MAM
2. Click Download → Job appears in Mamlarr dashboard
3. Status: "Downloading" → Torrent added to Transmission
4. Status: "Seeding" → Tracking seeding hours (target: 72h)
5. Status: "Processing" → Copying & applying metadata
6. Status: "Completed" → File in `./downloads/` folder
7. Torrent removed from Transmission (if auto-remove enabled)

### File Output:
```
./downloads/
├── Andy_Weir_-_Project_Hail_Mary.m4b
├── Andy_Weir_-_Project_Hail_Mary.m4b.metadata.json
└── Stephen_King_-_The_Stand.m4b
    └── Stephen_King_-_The_Stand.m4b.metadata.json
```

## 🔐 Security Notes

- Keep `.env` file secure (contains credentials)
- Don't commit `.env` to git (already in `.gitignore`)
- Use strong API keys
- Consider using secrets management in production

## 📝 Next Steps After Testing

1. Verify downloads work end-to-end
2. Check metadata is correctly applied
3. Test with AudiobookShelf import
4. Monitor seeding compliance (72 hours)
5. Adjust settings as needed via UI

---

**Ready to test!** Start with `docker-compose up -d` 🚀
