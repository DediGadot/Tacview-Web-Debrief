# DCS Mission Debrief - Render.com Deployment Guide

## Overview
This Flask application has been optimized for deployment on Render.com with the following enhancements:

## Key Changes Made

### 1. Production-Ready Configuration
- **Environment Variables**: Added support for environment-based configuration
- **Secret Key**: Uses `SECRET_KEY` environment variable for security
- **Upload Limits**: Configurable via `MAX_UPLOAD_SIZE` environment variable
- **Debug Mode**: Controlled via `FLASK_DEBUG` environment variable

### 2. Enhanced Error Handling
- **Logging**: Comprehensive logging for production debugging
- **Health Check**: Added `/health` endpoint for monitoring
- **Upload Safety**: Better error handling and file validation
- **Graceful Failures**: Proper error messages and cleanup

### 3. Optimized Render Configuration
- **Worker Configuration**: 2 workers with 120-second timeout
- **Health Monitoring**: Automatic health checks via `/health` endpoint
- **Persistent Storage**: 1GB disk for uploaded files and analysis results
- **Environment Variables**: Secure configuration management

## Deployment Steps

### 1. Connect Repository to Render
1. Log into your Render.com account
2. Click "New +" → "Web Service"
3. Connect your GitHub repository

### 2. Configure Service Settings
- **Name**: `dcs-mission-debrief`
- **Environment**: `Python`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --timeout 120 --workers 2 --worker-class sync app:app`

### 3. Environment Variables
Set these in the Render dashboard:
- `FLASK_DEBUG`: `false`
- `MAX_UPLOAD_SIZE`: `100` (MB)
- `SECRET_KEY`: Generate a secure random string
- `PYTHON_VERSION`: `3.11.0`

### 4. Configure Disk Storage
- **Name**: `dcs-mission-data`
- **Mount Path**: `/opt/render/project/src`
- **Size**: `1 GB`

## Features

### Health Check Endpoint
- **URL**: `https://your-app.onrender.com/health`
- **Purpose**: Monitors application health and disk access
- **Returns**: JSON status with system information

### File Upload Limits
- **Default**: 100MB per file
- **Configurable**: Via `MAX_UPLOAD_SIZE` environment variable
- **Supports**: Both DCS.log (optional) and debrief.log (required)

### Persistent Storage
- Uploaded files stored in `/uploads/`
- Analysis results stored in `/results/`
- Data persists across deployments

## Monitoring and Debugging

### Logs
- View logs in Render dashboard under "Logs" tab
- Detailed logging for upload and analysis processes
- Error tracking with request IDs

### Health Monitoring
```bash
curl https://your-app.onrender.com/health
```

Response example:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-14T20:30:00Z",
  "upload_dir_writable": true,
  "results_dir_writable": true,
  "max_upload_size_mb": 100
}
```

## Production Considerations

### Performance
- 2 Gunicorn workers handle concurrent requests
- 120-second timeout for large file processing
- Persistent disk prevents data loss

### Security
- Environment-based secret key management
- File type validation and sanitization
- Secure filename handling

### Scalability
- Can increase workers based on traffic
- Disk storage can be expanded as needed
- Health checks ensure service reliability

## Local Development vs Production

### Local Development
```bash
export FLASK_DEBUG=true
export PORT=5000
python app.py
```

### Production (Render)
- Uses Gunicorn WSGI server
- Environment variables from Render dashboard
- Persistent disk storage
- Automatic health monitoring

## Troubleshooting

### Common Issues
1. **Upload Failures**: Check disk space and file permissions
2. **Analysis Timeouts**: Increase timeout in start command
3. **Memory Issues**: Reduce workers or increase plan size

### Debug Steps
1. Check `/health` endpoint
2. Review logs in Render dashboard
3. Verify environment variables
4. Test with smaller files first

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `SECRET_KEY` | (required) | Flask secret key |
| `MAX_UPLOAD_SIZE` | `100` | Max upload size in MB |
| `PORT` | `5000` | Server port (set by Render) |
| `PYTHON_VERSION` | `3.11.0` | Python version |

## Next Steps
1. Deploy to Render using the provided configuration
2. Test with sample mission files
3. Monitor performance and adjust resources as needed
4. Set up custom domain if required 