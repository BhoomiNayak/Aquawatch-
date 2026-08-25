import 'package:flutter/material.dart';
import 'screens/home_screen.dart';
import 'screens/guidance_screen.dart';

void main() {
  runApp(const AquaWatchApp());
}

class AquaWatchApp extends StatelessWidget {
  const AquaWatchApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AquaWatch',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1A73E8),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        appBarTheme: const AppBarTheme(
          centerTitle: true,
          elevation: 0,
        ),
      ),
      initialRoute: '/',
      routes: {
        '/': (context) => const HomeScreen(),
        '/guidance': (context) => const GuidanceScreen(),
      },
    );
  }
}
