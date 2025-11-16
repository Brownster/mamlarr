# 🎉 Ready for End-to-End Testing!

Everything is set up and ready to test with real connections.

## ✅ What's Been Prepared

1. **Docker Configuration**
   - ✓ Updated `docker-compose.yml` with all environment variables
   - ✓ Added volume mounts for data persistence and downloads
   - ✓ Created `.env` file (ready for your credentials)
   - ✓ Added ffmpeg to Docker image for audio processing

2. **Documentation**
   - ✓ `DOCKER_SETUP.md` - Complete setup and troubleshooting guide
   - ✓ `.env.example` - Template with all configuration options
   - ✓ `start-docker.sh` - Quick-start script

3. **Directories**
   - ✓ `./data` - For settings persistence
   - ✓ `./downloads` - For processed audiobooks

## 🚀 Quick Start (3 Steps)

### Step 1: Configure Your Credentials

Edit the `.env` file with your real credentials:

```bash
nano .env
```

**Required changes:**
```bash
# Set any API key you want (you'll use this in AudioBookRequest)
MAM_SERVICE_API_KEY=your-secret-key-here

# Get from MyAnonamouse (see guide below)
MAM_SERVICE_MAM_SESSION_ID=your-actual-mam-cookie

# Your seedbox details
MAM_SERVICE_TRANSMISSION_URL=http://your-seedbox.com:9091/transmission/rpc
MAM_SERVICE_TRANSMISSION_USERNAME=your-username
MAM_SERVICE_TRANSMISSION_PASSWORD=your-password

# IMPORTANT: Disable mock mode!
MAM_SERVICE_USE_MOCK_DATA=false
```

**Getting Your MAM Session Cookie:**
1. Go to https://www.myanonamouse.net and log in
2. Press **F12** (open DevTools)
3. Go to **Application** → **Cookies** → `https://www.myanonamouse.net`
4. Find cookie named `mam_id`
5. Copy the **Value**
6. Paste it into `.env` as `MAM_SERVICE_MAM_SESSION_ID`

### Step 2: Start Docker Containers

```bash
./start-docker.sh
```

Or manually:
```bash
docker-compose build
docker-compose up -d
docker-compose logs -f  # Watch logs
```

### Step 3: Configure Settings via UI

**Option A: Web UI (Recommended)**
1. Open: http://localhost:8800/mamlarr/settings
2. Enter your MAM session cookie
3. Enter Transmission details
4. Click **"Test Connection"** to verify Transmission
5. Save settings

**Option B: Environment Variables (Already Done)**
- Your `.env` file settings are automatically loaded

## 🧪 Testing the Complete Flow

### 1. Verify Services Are Running

```bash
# Check containers
docker-compose ps

# Check health
curl http://localhost:8800/health

# View logs
docker-compose logs -f
```

**Expected Output:**
- AudioBookRequest: http://localhost:8000 ✓
- Mamlarr Dashboard: http://localhost:8800/mamlarr/ ✓
- Logs showing: "MamService: started indexer_id=801001"

### 2. Configure AudioBookRequest

1. Go to http://localhost:8000
2. Navigate to Settings → Prowlarr
3. Configure:
   - **URL**: `http://localhost:8800`
   - **API Key**: (same as `MAM_SERVICE_API_KEY` from .env)
4. Test connection
5. Should see **"MyAnonamouse"** indexer available

### 3. Download a Test Audiobook

1. In AudioBookRequest, search for an audiobook
2. Click **Download** on any result
3. Watch the Mamlarr dashboard: http://localhost:8800/mamlarr/

**Expected Flow:**
```
Search → Download → Mamlarr receives request
                 ↓
         Status: "Downloading" (torrent added to Transmission)
                 ↓
         Status: "Seeding" (tracking hours toward 72h goal)
                 ↓
         Status: "Processing" (copying files, applying metadata)
                 ↓
         Status: "Completed" ✓
                 ↓
         File appears in: ./downloads/
```

### 4. Verify the Output

```bash
# Check downloaded files
ls -lh downloads/

# Check metadata file
cat downloads/*.metadata.json

# Check embedded metadata (if m4b file)
ffprobe downloads/*.m4b 2>&1 | grep -A 10 "Metadata:"
```

**Expected Files:**
```
downloads/
├── Author_Name_-_Book_Title.m4b              # Audio file
└── Author_Name_-_Book_Title.m4b.metadata.json # Metadata sidecar
```

**Metadata JSON Example:**
```json
{
  "title": "Book Title",
  "authors": ["Author Name"],
  "narrators": ["Narrator Name"],
  "series": null,
  "asin": "B123456789",
  "description": "Book description...",
  "publishDate": "2023-01-01T00:00:00Z",
  "cover": "https://www.myanonamouse.net/covers/..."
}
```

## 📊 Monitoring

### Watch Job Progress

**Via Web UI:**
- Dashboard: http://localhost:8800/mamlarr/
- Job Detail: http://localhost:8800/mamlarr/jobs/{job-id}

**Via Logs:**
```bash
# All logs
docker-compose logs -f

# Only errors
docker-compose logs -f | grep -i error

# Only mamlarr service
docker-compose logs -f | grep mamlarr
```

### Check Transmission

1. Log into your seedbox
2. Open Transmission web interface
3. Should see torrent being downloaded/seeded
4. After 72 hours (or your target), torrent will be auto-removed

## 🔧 Troubleshooting

### Container Won't Start
```bash
# Check logs for errors
docker-compose logs

# Rebuild if needed
docker-compose build --no-cache
docker-compose up -d
```

### Can't Connect to Transmission
```bash
# Test RPC connection manually
curl -u "user:pass" http://your-seedbox:9091/transmission/rpc

# Check settings in UI
open http://localhost:8800/mamlarr/settings
```

### MAM Authentication Failed
- Cookie may have expired - get a fresh one
- Make sure you copied the entire value
- Check you're still logged into MAM in browser

### Files Not Appearing in Downloads
- Check logs: `docker-compose logs -f`
- Verify seeding is complete
- Check `MAM_SERVICE_SEED_TARGET_HOURS` setting
- Look for processing errors in logs

### ffmpeg Errors
```bash
# Verify ffmpeg is installed in container
docker-compose exec abr-mamlarr ffmpeg -version

# If missing, rebuild:
docker-compose build --no-cache
```

## 🎯 Success Criteria

You'll know it's working when:

- ✅ Dashboard shows active downloads
- ✅ Transmission shows torrent downloading
- ✅ Job status updates: Downloading → Seeding → Processing → Completed
- ✅ File appears in `./downloads/` folder
- ✅ Metadata file created (`.metadata.json`)
- ✅ Audio file has embedded metadata (if m4b)
- ✅ Torrent removed from Transmission (if auto-remove enabled)

## 📖 Full Documentation

- **Docker Setup**: See `DOCKER_SETUP.md`
- **Metadata Features**: See `METADATA_FEATURES.md`
- **Deployment Guide**: See `DEPLOYMENT.md`
- **Project Summary**: See `FINAL_SUMMARY.md`

## 🛑 Stopping the Containers

```bash
# Stop containers (data persists)
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

## 🔄 Making Changes

### Code Changes
```bash
git pull  # Get latest code
docker-compose build
docker-compose up -d
```

### Configuration Changes
```bash
nano .env  # Edit settings
docker-compose restart  # Apply changes
```

---

## 🎉 You're Ready!

1. **Edit `.env`** with your credentials
2. **Run `./start-docker.sh`**
3. **Configure settings** at http://localhost:8800/mamlarr/settings
4. **Test a download!**

---

**Questions or issues?** Check the logs first: `docker-compose logs -f`

**Happy testing!** 🚀
