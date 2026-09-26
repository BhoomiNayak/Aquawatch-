import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

class ApiService {
  // Change this to your machine's local IP for physical device testing
  // For Android emulator use: http://10.0.2.2:8001/api/v1
  // For physical device use: http://<YOUR_LOCAL_IP>:8001/api/v1
  static const String baseUrl = 'http://192.168.0.108:8002/api/v1';

  // Timeout duration
  static const Duration timeout = Duration(seconds: 60);

  // Max retries
  static const int maxRetries = 2;

  /// Upload photo and get analysis results from backend.
  /// Retries up to [maxRetries] times on network errors.
  static Future<Map<String, dynamic>> analyzeWater({
    required File imageFile,
    required double latitude,
    required double longitude,
    required String contaminationType,
    String? reporterName,
    String? notes,
  }) async {
    Exception? lastError;

    for (int attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          // Wait before retry (exponential backoff)
          await Future.delayed(Duration(seconds: attempt * 2));
        }

        var uri = Uri.parse('$baseUrl/analyze-water');
        var request = http.MultipartRequest('POST', uri);

        // Add image file
        var stream = http.ByteStream(imageFile.openRead());
        var length = await imageFile.length();

        // Determine content type from extension
        String ext = imageFile.path.split('.').last.toLowerCase();
        MediaType contentType;
        if (ext == 'png') {
          contentType = MediaType('image', 'png');
        } else {
          contentType = MediaType('image', 'jpeg');
        }

        var multipartFile = http.MultipartFile(
          'image',
          stream,
          length,
          filename: 'water_photo.$ext',
          contentType: contentType,
        );
        request.files.add(multipartFile);

        // Add form fields
        request.fields['latitude'] = latitude.toString();
        request.fields['longitude'] = longitude.toString();
        request.fields['contamination_type'] = contaminationType;
        if (reporterName != null && reporterName.isNotEmpty) {
          request.fields['reporter_name'] = reporterName;
        }
        if (notes != null && notes.isNotEmpty) {
          request.fields['notes'] = notes;
        }

        // Send request with timeout
        var streamedResponse = await request.send().timeout(timeout);
        var response = await http.Response.fromStream(streamedResponse);

        if (response.statusCode == 201) {
          return json.decode(response.body) as Map<String, dynamic>;
        } else if (response.statusCode >= 500) {
          // Server error — retry
          lastError = Exception('Server error (${response.statusCode}). Retrying...');
          continue;
        } else {
          // Client error (4xx) — don't retry
          var body = json.decode(response.body);
          throw Exception(body['detail'] ?? 'Upload failed (${response.statusCode})');
        }
      } on SocketException {
        lastError = Exception('Cannot connect to server. Check your internet connection.');
        continue;
      } on HttpException catch (e) {
        lastError = Exception('Network error: ${e.message}');
        continue;
      } on FormatException {
        throw Exception('Invalid response from server.');
      } catch (e) {
        if (e is Exception && e.toString().contains('TimeoutException')) {
          lastError = Exception('Request timed out. Please try again.');
          continue;
        }
        rethrow;
      }
    }

    // All retries failed
    throw lastError ?? Exception('Upload failed after $maxRetries retries.');
  }

  /// Fetch a single report by id, including the async `satellite_verdict`.
  /// Used to poll for the background satellite enrichment result.
  static Future<Map<String, dynamic>> getReport(String reportId) async {
    final uri = Uri.parse('$baseUrl/reports/$reportId');
    final response = await http.get(uri).timeout(const Duration(seconds: 20));
    if (response.statusCode == 200) {
      return json.decode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to fetch report (${response.statusCode})');
  }

  /// Check if the backend is reachable.
  static Future<bool> healthCheck() async {
    try {
      var response = await http.get(
        Uri.parse('$baseUrl/health'),
      ).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}
