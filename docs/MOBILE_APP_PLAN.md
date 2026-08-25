# AquaWatch - Mobile App Plan (Flutter)

## Overview

A simplified Flutter app that captures a photo, records GPS, lets the user select contamination type, uploads everything to the backend, and displays the analysis result. No on-device ML, no offline queue for the demo.

---

## Screen Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│              │     │              │     │              │
│    HOME      │────▶│   GUIDANCE   │────▶│   CAMERA     │
│   SCREEN     │     │   SCREEN     │     │   SCREEN     │
│              │     │              │     │              │
│  [Report     │     │  Instructions│     │  [Capture]   │
│   Water]     │     │  for taking  │     │              │
│              │     │  a good photo│     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                                                │
                                                ▼ photo captured
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│              │     │              │     │              │
│   RESULT     │◀────│  SUBMITTING  │◀────│  REPORT      │
│   SCREEN     │     │  (loading)   │     │  FORM        │
│              │     │              │     │              │
│  Color-coded │     │  Uploading   │     │  - Photo     │
│  result card │     │  & analyzing │     │    preview   │
│  + breakdown │     │  ...         │     │  - Type      │
│              │     │              │     │  - Name      │
│  [Report     │     │              │     │  [Submit]    │
│   Another]   │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

## Screens Detail

### 1. Home Screen (`home_screen.dart`)

Simple landing screen with app branding and a single CTA.

```
┌─────────────────────────┐
│                         │
│      🌊 AquaWatch       │
│                         │
│   "Help monitor your    │
│    local water bodies"  │
│                         │
│                         │
│   ┌─────────────────┐   │
│   │  Report Water   │   │
│   │     Quality     │   │
│   └─────────────────┘   │
│                         │
│   Reports submitted: 23 │
│                         │
└─────────────────────────┘
```

- Large "Report Water Quality" button
- Optional: show count of total reports submitted (from backend)
- AppBar with AquaWatch title

### 2. Guidance Screen (`guidance_screen.dart`)

Quick instructions before opening camera.

```
┌─────────────────────────┐
│  ← Back                 │
│                         │
│   📸 Photo Tips         │
│                         │
│   ✓ Point camera at     │
│     the water surface   │
│                         │
│   ✓ Keep camera level   │
│     (not angled)        │
│                         │
│   ✓ Avoid sun           │
│     reflections         │
│                         │
│   ✓ Include only water  │
│     (no sky/buildings)  │
│                         │
│   ┌─────────────────┐   │
│   │  Open Camera    │   │
│   └─────────────────┘   │
│                         │
└─────────────────────────┘
```

- 4-5 simple tips with icons
- "Open Camera" button triggers camera
- GPS permission requested here (background)

### 3. Camera Screen (`camera_screen.dart`)

Uses `image_picker` package for simplicity (no custom camera UI needed for demo).

```dart
// Using image_picker — simpler than camera package
final ImagePicker picker = ImagePicker();
final XFile? photo = await picker.pickImage(
    source: ImageSource.camera,
    maxWidth: 1280,
    maxHeight: 1280,
    imageQuality: 85,
);
```

- Max resolution 1280px (keeps file size reasonable)
- JPEG quality 85% (good balance of quality vs upload speed)
- After capture → navigate to Report Form with photo file

### 4. Report Form Screen (`report_form_screen.dart`)

```
┌─────────────────────────┐
│  ← Back                 │
│                         │
│  ┌───────────────────┐  │
│  │                   │  │
│  │   Photo Preview   │  │
│  │   (thumbnail)     │  │
│  │                   │  │
│  └───────────────────┘  │
│                         │
│  📍 Location captured   │
│  12.9373°N, 77.6784°E  │
│                         │
│  Contamination Type:    │
│  ┌───────────────────┐  │
│  │ Industrial Disch ▼│  │
│  └───────────────────┘  │
│                         │
│  Your Name (optional):  │
│  ┌───────────────────┐  │
│  │                   │  │
│  └───────────────────┘  │
│                         │
│  Notes (optional):      │
│  ┌───────────────────┐  │
│  │                   │  │
│  └───────────────────┘  │
│                         │
│  ┌─────────────────┐   │
│  │    Submit        │   │
│  └─────────────────┘   │
│                         │
└─────────────────────────┘
```

- Photo thumbnail at top
- GPS coordinates shown (auto-captured)
- Contamination type dropdown (required)
- Reporter name (optional text field)
- Notes (optional text area)
- Submit button → calls API

### 5. Result Screen (`result_screen.dart`)

```
┌─────────────────────────┐
│                         │
│   Analysis Complete ✓   │
│                         │
│  ┌───────────────────┐  │
│  │                   │  │
│  │   ██████████████  │  │
│  │   HIGH RISK       │  │ ← Color-coded card (red/yellow/green)
│  │   Score: 72.5     │  │
│  │                   │  │
│  │   Water Body:     │  │
│  │   Bellandur Lake  │  │
│  │                   │  │
│  └───────────────────┘  │
│                         │
│  Breakdown:             │
│  ├─ Algae: 45.8%       │
│  ├─ Foam: 32.1%        │
│  └─ Clarity: Low       │
│                         │
│  FU Index: 18           │
│  (Brown-Red water)      │
│                         │
│  ┌─────────────────┐   │
│  │ Report Another  │   │
│  └─────────────────┘   │
│                         │
└─────────────────────────┘
```

- Large color-coded result card (green/yellow/red background)
- Risk level + numeric score
- Matched water body name
- Analysis breakdown (algae %, foam %, clarity)
- Forel-Ule index with color name
- "Report Another" button → back to Home

---

## Flutter Packages (pubspec.yaml)

```yaml
dependencies:
  flutter:
    sdk: flutter
  
  # Camera & Photo
  image_picker: ^1.0.4          # Simple camera/gallery access
  
  # Location
  geolocator: ^10.1.0           # GPS coordinates
  permission_handler: ^11.0.1   # Permission requests
  
  # HTTP
  http: ^1.1.0                  # API calls
  dio: ^5.3.3                   # Alternative: better multipart support
  
  # UI
  flutter_spinkit: ^5.2.0       # Loading spinners (optional)
```

---

## Services

### `api_service.dart`

```dart
class ApiService {
  static const String baseUrl = 'http://10.0.2.2:8000/api/v1'; // Android emulator
  // For physical device: use your machine's local IP
  
  /// Upload photo and get analysis results
  Future<AnalysisResult> analyzeWater({
    required File image,
    required double latitude,
    required double longitude,
    required String contaminationType,
    String? reporterName,
    String? notes,
  }) async {
    // Multipart form upload
    // Returns parsed AnalysisResult
  }
}
```

### `location_service.dart`

```dart
class LocationService {
  /// Get current GPS position
  /// Request permission if not granted
  /// Returns (latitude, longitude) or throws
  Future<Position> getCurrentPosition() async {
    // Check permission
    // Get position with high accuracy
    // Timeout after 10 seconds
  }
}
```

---

## Data Model

### `report.dart`

```dart
class AnalysisResult {
  final String reportId;
  final String waterBodyName;
  final double distanceMeters;
  
  // Analysis
  final int forelUleIndex;
  final String forelUleColor;
  final double algaePercentage;
  final bool foamDetected;
  final double foamCoverage;
  final double turbidityScore;
  
  // Risk
  final double compositeScore;
  final String riskLevel; // "low", "moderate", "high"
}
```

---

## GPS Strategy

1. **Request permission** on Guidance Screen (before camera opens)
2. **Start listening** for location in background
3. **Get position** when form is submitted (or use cached recent position)
4. **Accuracy**: `LocationAccuracy.high` — targets <10m
5. **Timeout**: 10 seconds — if no GPS fix, show error and retry option
6. **Emulator**: Use Android Emulator's location settings to simulate Bengaluru coordinates

---

## Error Handling

| Error | User Message | Action |
|-------|-------------|--------|
| No GPS permission | "Location is required to tag your report" | Show settings button |
| GPS timeout | "Could not get your location. Please try again outdoors" | Retry button |
| No internet | "No internet connection. Please try again later" | Retry button |
| Upload failed | "Upload failed. Check your connection" | Retry with same data |
| Server error | "Something went wrong. Please try again" | Retry button |
| Image too large | "Photo is too large" | Won't happen (capped at 1280px) |

---

## Network Configuration

### Android Emulator
```dart
static const String baseUrl = 'http://10.0.2.2:8000/api/v1';
// 10.0.2.2 = host machine loopback in Android emulator
```

### Physical Device (same WiFi)
```dart
static const String baseUrl = 'http://192.168.x.x:8000/api/v1';
// Replace with actual machine IP
```

### Android Network Security (for HTTP in demo)
Add to `android/app/src/main/AndroidManifest.xml`:
```xml
<application
    android:usesCleartextTraffic="true"
    ...>
```

---

## Nice-to-Have (If Time Permits)

- **Offline queue**: Save report locally if no internet, auto-submit when connected
- **Photo retake**: Allow retaking photo from form screen
- **History screen**: Show user's past submissions
- **Multiple photos**: Allow 2-3 photos per report
- **Dark mode**: Respect system theme
