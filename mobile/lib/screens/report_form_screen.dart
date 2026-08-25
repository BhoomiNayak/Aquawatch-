import 'dart:io';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/location_service.dart';
import 'result_screen.dart';

class ReportFormScreen extends StatefulWidget {
  final File imageFile;

  const ReportFormScreen({super.key, required this.imageFile});

  @override
  State<ReportFormScreen> createState() => _ReportFormScreenState();
}

class _ReportFormScreenState extends State<ReportFormScreen> {
  final _formKey = GlobalKey<FormState>();
  String _contaminationType = 'others';
  String _reporterName = '';
  String _notes = '';
  bool _isSubmitting = false;
  double? _latitude;
  double? _longitude;
  String _locationStatus = 'Getting location...';

  final List<Map<String, String>> _contaminationTypes = [
    {'value': 'industrial_discharge', 'label': 'Industrial Discharge'},
    {'value': 'sewage', 'label': 'Sewage'},
    {'value': 'algal_bloom', 'label': 'Algal Bloom'},
    {'value': 'solid_waste', 'label': 'Solid Waste'},
    {'value': 'agricultural_runoff', 'label': 'Agricultural Runoff'},
    {'value': 'fish_kill', 'label': 'Fish Kill'},
    {'value': 'foam', 'label': 'Foam'},
    {'value': 'oil_spill', 'label': 'Oil Spill'},
    {'value': 'others', 'label': 'Others'},
  ];

  @override
  void initState() {
    super.initState();
    _getLocation();
  }

  Future<void> _getLocation() async {
    try {
      final position = await LocationService.getCurrentPosition();
      setState(() {
        _latitude = position.latitude;
        _longitude = position.longitude;
        _locationStatus = '${position.latitude.toStringAsFixed(4)}, ${position.longitude.toStringAsFixed(4)}';
      });
    } catch (e) {
      setState(() {
        _locationStatus = 'Location unavailable: $e';
      });
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_latitude == null || _longitude == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Waiting for GPS location...')),
      );
      return;
    }

    _formKey.currentState!.save();
    setState(() { _isSubmitting = true; });

    try {
      final result = await ApiService.analyzeWater(
        imageFile: widget.imageFile,
        latitude: _latitude!,
        longitude: _longitude!,
        contaminationType: _contaminationType,
        reporterName: _reporterName.isEmpty ? null : _reporterName,
        notes: _notes.isEmpty ? null : _notes,
      );

      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (context) => ResultScreen(result: result),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() { _isSubmitting = false; });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Upload failed: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Submit Report')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Photo preview
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.file(
                  widget.imageFile,
                  height: 200,
                  width: double.infinity,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(height: 16),

              // Location
              Row(
                children: [
                  Icon(Icons.location_on, size: 18, color: Colors.grey[600]),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      _locationStatus,
                      style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Contamination type
              const Text('Contamination Type', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _contaminationType,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                ),
                items: _contaminationTypes.map((t) {
                  return DropdownMenuItem(value: t['value'], child: Text(t['label']!));
                }).toList(),
                onChanged: (val) { setState(() { _contaminationType = val!; }); },
              ),
              const SizedBox(height: 16),

              // Reporter name
              const Text('Your Name (optional)', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextFormField(
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'Enter your name',
                ),
                onSaved: (val) { _reporterName = val ?? ''; },
              ),
              const SizedBox(height: 16),

              // Notes
              const Text('Notes (optional)', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextFormField(
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'Any observations...',
                ),
                maxLines: 3,
                onSaved: (val) { _notes = val ?? ''; },
              ),
              const SizedBox(height: 24),

              // Submit button
              SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(
                  onPressed: _isSubmitting ? null : _submit,
                  child: _isSubmitting
                      ? const SizedBox(
                          width: 24, height: 24,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Submit Report', style: TextStyle(fontSize: 16)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
