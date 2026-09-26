import 'dart:async';
import 'package:flutter/material.dart';

import '../services/api_service.dart';

class ResultScreen extends StatefulWidget {
  final Map<String, dynamic> result;

  const ResultScreen({super.key, required this.result});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  Timer? _pollTimer;
  Map<String, dynamic>? _satelliteVerdict;
  String _satelliteStatus = 'processing';
  int _pollCount = 0;
  static const int _maxPolls = 40; // ~2 min at 3s cadence

  @override
  void initState() {
    super.initState();
    // POST response carries report_id + satellite_status="processing".
    _satelliteStatus =
        (widget.result['satellite_status'] ?? 'processing').toString();
    final reportId = widget.result['report_id']?.toString();
    if (reportId != null && _isPending(_satelliteStatus)) {
      _startPolling(reportId);
    }
  }

  bool _isPending(String status) =>
      status == 'processing' || status == 'pending';

  void _startPolling(String reportId) {
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (timer) async {
      _pollCount++;
      try {
        final report = await ApiService.getReport(reportId);
        final verdict = report['satellite_verdict'] as Map<String, dynamic>?;
        final status = (verdict?['status'] ?? 'processing').toString();
        if (!mounted) return;
        setState(() {
          _satelliteVerdict = verdict;
          _satelliteStatus = status;
        });
        if (!_isPending(status) || _pollCount >= _maxPolls) {
          timer.cancel();
        }
      } catch (_) {
        // Transient network error — keep polling until the cap.
        if (_pollCount >= _maxPolls) {
          timer.cancel();
          if (mounted) setState(() => _satelliteStatus = 'error');
        }
      }
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final result = widget.result;
    final risk = result['risk'] ?? {};
    final waterBody = result['water_body'] ?? {};
    final analysis = result['analysis'] ?? {};
    final forelUle = analysis['forel_ule'] ?? {};
    final algae = analysis['algae'] ?? {};
    final foam = analysis['foam'] ?? {};
    final turbidity = analysis['turbidity'] ?? {};
    final oilSheen = analysis['oil_sheen'] ?? {};
    final colorAbnormality = analysis['color_abnormality'] ?? {};
    final debris = analysis['surface_debris'] ?? {};
    final yolo = result['yolo_detection'] ?? {};
    final efficientnet = result['efficientnet'] ?? {};

    final riskLevel = risk['risk_level'] ?? 'unknown';
    final score = (risk['composite_score'] ?? 0).toDouble();

    Color riskColor;
    switch (riskLevel) {
      case 'high':
        riskColor = const Color(0xFFDC3545);
        break;
      case 'moderate':
        riskColor = const Color(0xFFFFC107);
        break;
      default:
        riskColor = const Color(0xFF28A745);
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Analysis Result')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // Risk card
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: riskColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: riskColor.withValues(alpha: 0.3)),
              ),
              child: Column(
                children: [
                  Text(
                    '${riskLevel.toUpperCase()} RISK',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: riskColor,
                      letterSpacing: 2,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    score.toStringAsFixed(1),
                    style: TextStyle(
                      fontSize: 48,
                      fontWeight: FontWeight.bold,
                      color: riskColor,
                    ),
                  ),
                  Text(
                    'Risk Score / 100',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    waterBody['name'] ?? 'Unknown Water Body',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                  if (waterBody['distance_meters'] != null)
                    Text(
                      '${(waterBody['distance_meters'] as num).toStringAsFixed(0)}m away',
                      style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Satellite corroboration (async, polled)
            _buildSatelliteSection(),
            const SizedBox(height: 16),

            // AI Classification (EfficientNet + YOLO)
            _buildSection('AI Classification', [
              _buildChip(
                'Water Quality',
                efficientnet['prediction'] == 'bad' ? 'Polluted' : 'Clean',
                efficientnet['prediction'] == 'bad' ? Colors.red : Colors.green,
                '${((efficientnet['confidence'] ?? 0) * 100).toStringAsFixed(0)}%',
              ),
              const SizedBox(height: 8),
              _buildChip(
                'Water Type',
                (yolo['prediction'] ?? 'unknown').toString().toUpperCase(),
                _getYoloColor(yolo['prediction'] ?? 'unknown'),
                '${((yolo['confidence'] ?? 0) * 100).toStringAsFixed(0)}%',
              ),
            ]),
            const SizedBox(height: 16),

            // Detailed CV Analysis
            _buildSection('Detailed Analysis', [
              _buildAnalysisRow(
                'Forel-Ule Index',
                '${forelUle['fu_index'] ?? '-'}',
                forelUle['fu_color_name'] ?? '',
                Icons.palette,
              ),
              _buildProgressRow('Algae Coverage', (algae['algae_percentage'] ?? 0).toDouble(), Colors.green),
              _buildProgressRow('Foam Coverage', (foam['foam_coverage_percentage'] ?? 0).toDouble(), Colors.grey),
              _buildProgressRow('Clarity', (turbidity['turbidity_score'] ?? 0).toDouble(), Colors.blue),
              _buildProgressRow('Oil Sheen', (oilSheen['oil_coverage_percentage'] ?? 0).toDouble(), Colors.purple),
              _buildProgressRow('Color Abnormality', (colorAbnormality['color_abnormality_score'] ?? 0).toDouble(), Colors.orange),
              _buildProgressRow('Surface Debris', (debris['contour_density'] ?? 0).toDouble(), Colors.brown),
            ]),
            const SizedBox(height: 16),

            // Descriptions
            _buildSection('Summary', [
              _buildInfoRow('Water Color', forelUle['fu_color_name'] ?? '-'),
              _buildInfoRow('Algae', algae['severity'] ?? '-'),
              _buildInfoRow('Foam', foam['foam_detected'] == true ? 'Detected (${(foam['foam_coverage_percentage'] ?? 0).toStringAsFixed(1)}%)' : 'Not detected'),
              _buildInfoRow('Clarity', turbidity['clarity_description'] ?? '-'),
              _buildInfoRow('Oil Sheen', oilSheen['confidence'] ?? '-'),
              _buildInfoRow('Debris', debris['description'] ?? '-'),
            ]),
            const SizedBox(height: 24),

            // Report another
            SizedBox(
              width: double.infinity,
              height: 52,
              child: FilledButton.icon(
                onPressed: () {
                  Navigator.of(context).popUntil((route) => route.isFirst);
                },
                icon: const Icon(Icons.add_a_photo),
                label: const Text('Report Another', style: TextStyle(fontSize: 16)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Satellite corroboration section ──────────────────────────────────────
  Widget _buildSatelliteSection() {
    final verdict = _satelliteVerdict;
    final status = (verdict?['status'] ?? _satelliteStatus).toString();

    // 1. Still processing -> badge + spinner
    if (_isPending(status)) {
      return _satelliteContainer(
        Colors.blueGrey,
        Row(
          children: [
            const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 12),
            Text(
              'Processing Satellite Data...',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: Colors.blueGrey[700],
              ),
            ),
          ],
        ),
      );
    }

    final confidence = (verdict?['spatial_confidence'] ?? '').toString();
    final unavailableStatus = status != 'done';

    // 2. Unavailable: status not done, OR low spatial confidence, OR no water
    if (unavailableStatus || confidence == 'low') {
      return _satelliteContainer(
        Colors.grey,
        Row(
          children: [
            Icon(Icons.satellite_alt, size: 18, color: Colors.grey[600]),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Satellite Corroboration Unavailable '
                '(Sub-pixel Target / No Open Water)',
                style: TextStyle(fontSize: 13, color: Colors.grey[700]),
              ),
            ),
          ],
        ),
      );
    }

    // 3. Done with a usable reading
    final ndci = verdict?['ndci'];
    final exceeds = verdict?['exceeds_clean_baseline'] == true;
    final corroboration = (verdict?['corroboration'] ?? '').toString();
    final mode = (verdict?['mode'] ?? '').toString();

    final String anomalyLabel;
    final Color anomalyColor;
    if (exceeds) {
      anomalyLabel = corroboration == 'elevated' ? 'ELEVATED' : 'WATCH';
      anomalyColor = corroboration == 'elevated'
          ? const Color(0xFFDC3545)
          : const Color(0xFFFFC107);
    } else {
      anomalyLabel = 'NOMINAL';
      anomalyColor = const Color(0xFF28A745);
    }

    final modeLabel =
        mode == 'cached_lake' ? 'Tracked Lake' : 'Dynamic Point Buffer';
    final confidenceLabel = confidence.isEmpty
        ? '-'
        : '${confidence[0].toUpperCase()}${confidence.substring(1)}';
    final ndciText = ndci is num ? ndci.toStringAsFixed(4) : '-';

    return _satelliteContainer(
      anomalyColor,
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.satellite_alt, size: 18, color: anomalyColor),
              const SizedBox(width: 8),
              const Text(
                'Satellite Corroboration',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: anomalyColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                  border:
                      Border.all(color: anomalyColor.withValues(alpha: 0.4)),
                ),
                child: Text(
                  anomalyLabel,
                  style: TextStyle(
                    color: anomalyColor,
                    fontWeight: FontWeight.w700,
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildInfoRow('NDCI (chlorophyll proxy)', ndciText),
          _buildInfoRow('vs clean baseline',
              exceeds ? 'Above baseline' : 'At/below baseline'),
          _buildInfoRow('Spatial confidence', confidenceLabel),
          _buildInfoRow('Source', modeLabel),
          const SizedBox(height: 6),
          Text(
            'Independent physical corroboration. Relative anomaly (not '
            'calibrated to absolute chlorophyll).',
            style: TextStyle(fontSize: 11, color: Colors.grey[500]),
          ),
        ],
      ),
    );
  }

  Widget _satelliteContainer(Color accent, Widget child) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: accent.withValues(alpha: 0.25)),
      ),
      child: child,
    );
  }

  Color _getYoloColor(String prediction) {
    switch (prediction) {
      case 'polluted':
        return Colors.red;
      case 'turbid':
        return Colors.orange;
      case 'clean':
        return Colors.green;
      default:
        return Colors.grey;
    }
  }

  Widget _buildSection(String title, List<Widget> children) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }

  Widget _buildChip(String label, String value, Color color, String confidence) {
    return Row(
      children: [
        Text('$label: ', style: TextStyle(color: Colors.grey[700], fontSize: 14)),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: color.withValues(alpha: 0.3)),
          ),
          child: Text(
            value,
            style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13),
          ),
        ),
        const SizedBox(width: 8),
        Text(confidence, style: TextStyle(color: Colors.grey[500], fontSize: 12)),
      ],
    );
  }

  Widget _buildProgressRow(String label, double value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 120,
            child: Text(label, style: TextStyle(color: Colors.grey[700], fontSize: 13)),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (value / 100).clamp(0.0, 1.0),
                backgroundColor: Colors.grey.shade200,
                color: color,
                minHeight: 8,
              ),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 40,
            child: Text(
              '${value.toStringAsFixed(1)}%',
              style: TextStyle(fontSize: 11, color: Colors.grey[600]),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnalysisRow(String label, String value, String subtitle, IconData icon) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 18, color: Colors.grey[600]),
          const SizedBox(width: 8),
          Text('$label: ', style: TextStyle(color: Colors.grey[700], fontSize: 14)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          if (subtitle.isNotEmpty) ...[
            const SizedBox(width: 6),
            Text('($subtitle)', style: TextStyle(color: Colors.grey[500], fontSize: 12)),
          ],
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.grey[700], fontSize: 13)),
          Flexible(
            child: Text(
              value,
              style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }
}
