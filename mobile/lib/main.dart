import 'package:flutter/material.dart';

void main() => runApp(const MakoloApp());

class MakoloApp extends StatefulWidget {
  const MakoloApp({super.key});

  @override
  State<MakoloApp> createState() => _MakoloAppState();
}

class _MakoloAppState extends State<MakoloApp> {
  var index = 0;
  static const labels = ['Maintenant', 'Découvrir', 'Makolo', 'En cours', 'Moi'];

  @override
  Widget build(BuildContext context) {
    const primary = Color(0xFF5232DB);
    const background = Color(0xFFFAF7F5);
    const ink = Color(0xFF0F172A);

    return MaterialApp(
      title: 'Makolo',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: background,
        colorScheme: const ColorScheme.light(
          primary: primary,
          secondary: Color(0xFFFF704D),
          surface: background,
          onSurface: ink,
        ),
      ),
      home: Scaffold(
        appBar: AppBar(title: const Text('Makolo mobile · Phase 0')),
        body: Center(
          child: Text(
            labels[index],
            style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700),
          ),
        ),
        bottomNavigationBar: NavigationBar(
          selectedIndex: index,
          onDestinationSelected: (value) => setState(() => index = value),
          destinations: const [
            NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Maintenant'),
            NavigationDestination(icon: Icon(Icons.explore_outlined), label: 'Découvrir'),
            NavigationDestination(icon: Icon(Icons.circle_outlined), label: 'Makolo'),
            NavigationDestination(icon: Icon(Icons.timeline_outlined), label: 'En cours'),
            NavigationDestination(icon: Icon(Icons.person_outline), label: 'Moi'),
          ],
        ),
      ),
    );
  }
}
