import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../design/makolo_mark.dart';

/// Guest shell: distinct from the Profile and Space shells.
/// Public navigation carries no personal identity or delegated authority.
class PublicExperienceShell extends StatelessWidget {
  const PublicExperienceShell({
    super.key,
    required this.current,
    required this.child,
  });

  final int current;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leadingWidth: 64,
        leading: IconButton(
          tooltip: 'Accueil Makolo',
          onPressed: () => context.go('/welcome'),
          icon: const MakoloMark(size: 36),
        ),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Compte',
            icon: const Icon(Icons.account_circle_outlined),
            onSelected: (value) => context.push(
              value == 'register' ? '/create-account' : '/login',
            ),
            itemBuilder: (context) => const [
              PopupMenuItem(value: 'login', child: Text('Connexion')),
              PopupMenuItem(value: 'register', child: Text('Créer un compte')),
            ],
          ),
        ],
      ),
      body: SafeArea(top: false, child: child),
      bottomNavigationBar: NavigationBar(
        selectedIndex: current,
        onDestinationSelected: (index) => context.go(switch (index) {
          0 => '/welcome',
          1 => '/discover',
          _ => '/spaces',
        }),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Accueil',
          ),
          NavigationDestination(
            icon: Icon(Icons.explore_outlined),
            selectedIcon: Icon(Icons.explore),
            label: 'Découvrir',
          ),
          NavigationDestination(
            icon: Icon(Icons.groups_outlined),
            selectedIcon: Icon(Icons.groups),
            label: 'Espaces',
          ),
        ],
      ),
    );
  }
}
