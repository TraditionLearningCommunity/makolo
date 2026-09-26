import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';

import '../design/makolo_theme.dart';
import '../navigation/destination.dart';

class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

  int _selected(String path) {
    final destinations = MakoloDestination.values;
    final index = destinations.indexWhere((destination) =>
        path == destination.path || path.startsWith('${destination.path}/'));
    return index < 0 ? 0 : index;
  }

  @override
  Widget build(BuildContext context) {
    final path = GoRouterState.of(context).uri.path;
    final selected = _selected(path);

    return Scaffold(
      body: SafeArea(child: child),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Material(
          color: Theme.of(context).colorScheme.surface,
          elevation: 8,
          child: SizedBox(
            height: 72,
            child: Row(
              children: [
                _NavButton(
                  destination: MakoloDestination.now,
                  icon: Icons.home_outlined,
                  selected: selected == 0,
                ),
                _NavButton(
                  destination: MakoloDestination.discover,
                  icon: Icons.explore_outlined,
                  selected: selected == 1,
                ),
                Expanded(
                  child: Semantics(
                    button: true,
                    label: 'Makolo',
                    child: IconButton(
                      tooltip: 'Makolo',
                      constraints: const BoxConstraints(
                        minWidth: 48,
                        minHeight: 48,
                      ),
                      onPressed: () => context.push('/mark'),
                      icon: Container(
                        width: 48,
                        height: 48,
                        padding: const EdgeInsets.all(10),
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: MakoloColors.indigo,
                        ),
                        child: SvgPicture.asset(
                          'assets/brand/makolo-mark-white.svg',
                        ),
                      ),
                    ),
                  ),
                ),
                _NavButton(
                  destination: MakoloDestination.ongoing,
                  icon: Icons.route_outlined,
                  selected: selected == 2,
                ),
                _NavButton(
                  destination: MakoloDestination.me,
                  icon: Icons.person_outline,
                  selected: selected == 3,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.destination,
    required this.icon,
    required this.selected,
  });

  final MakoloDestination destination;
  final IconData icon;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final color = selected
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.onSurfaceVariant;
    return Expanded(
      child: Semantics(
        button: true,
        selected: selected,
        label: destination.label,
        child: InkWell(
          onTap: () => context.go(destination.path),
          child: SizedBox(
            height: 64,
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: color),
                const SizedBox(height: 3),
                Text(
                  destination.label,
                  maxLines: 1,
                  style: TextStyle(
                    color: color,
                    fontSize: 11,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
