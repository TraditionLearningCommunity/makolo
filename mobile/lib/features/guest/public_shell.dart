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
          OutlinedButton(
            key: const Key('guest-login-action'),
            onPressed: () => context.push('/login'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              minimumSize: const Size(0, 40),
              visualDensity: VisualDensity.compact,
            ),
            child: const Text('Connexion'),
          ),
          const SizedBox(width: 8),
          OutlinedButton(
            key: const Key('guest-register-action'),
            onPressed: () => context.push('/create-account'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              minimumSize: const Size(0, 40),
              visualDensity: VisualDensity.compact,
            ),
            child: const Text("S'inscrire"),
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: SafeArea(top: false, child: child),
      bottomNavigationBar: NavigationBarTheme(
        data: NavigationBarThemeData(
          labelTextStyle: WidgetStateProperty.resolveWith((states) {
            final colors = Theme.of(context).colorScheme;
            return TextStyle(
              color: states.contains(WidgetState.selected)
                  ? colors.onSurface
                  : colors.onSurfaceVariant,
              fontWeight: states.contains(WidgetState.selected)
                  ? FontWeight.w700
                  : FontWeight.w600,
            );
          }),
        ),
        child: NavigationBar(
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
      ),
    );
  }
}
