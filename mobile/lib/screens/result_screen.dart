import 'package:flutter/material.dart';

class ResultScreen extends StatelessWidget {
  final Map<String, dynamic> result;

  const ResultScreen({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final risk = result['risk'] ?? {};
    final waterBody = result['water_body'] ?? {};
    final analysis = result['analysis'] ?? {};
    final forelUle = analysis['forel_ule'] ?? {};
    final algae = analysis['algae'] ?? {};
    final foam = analysis['foam'] ?? {};
    final turbidity = analysis['turbidity'] ?? {};

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
                    riskLevel.toUpperCase(),
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
            const SizedBox(height: 20),

            // Breakdown
            _buildSection('Analysis Breakdown', [
              _buildRow('Forel-Ule Index', '${forelUle['fu_index'] ?? '-'} (${forelUle['fu_color_name'] ?? '-'})'),
              _buildRow('Algae', '${(algae['algae_percentage'] ?? 0).toStringAsFixed(1)}% - ${algae['severity'] ?? '-'}'),
              _buildRow('Foam', foam['foam_detected'] == true ? '${(foam['foam_coverage_percentage'] ?? 0).toStringAsFixed(1)}% coverage' : 'Not detected'),
              _buildRow('Clarity', '${(turbidity['turbidity_score'] ?? 0).toStringAsFixed(1)}/100 - ${turbidity['clarity_description'] ?? '-'}'),
            ]),
            const SizedBox(height: 20),

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

  Widget _buildSection(String title, List<Widget> children) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
        const SizedBox(height: 8),
        ...children,
      ],
    );
  }

  Widget _buildRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.grey[700], fontSize: 14)),
          Flexible(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14), textAlign: TextAlign.right)),
        ],
      ),
    );
  }
}
