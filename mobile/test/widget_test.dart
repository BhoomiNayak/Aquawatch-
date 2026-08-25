import 'package:flutter_test/flutter_test.dart';

import 'package:aquawatch/main.dart';

void main() {
  testWidgets('App loads home screen', (WidgetTester tester) async {
    await tester.pumpWidget(const AquaWatchApp());
    expect(find.text('AquaWatch'), findsOneWidget);
    expect(find.text('Report Water Quality'), findsOneWidget);
  });
}
