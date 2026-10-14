import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';
import '../../platform/location/location_capability.dart';
import '../../platform/location/location_service.dart';
import '../../platform/location/discovery_location_context.dart';
import '../../platform/permissions/permission_gateway.dart';

enum OnboardingExit {
  skip,
  signIn,
  createAccount,
  continueGuest,
  continueAuthenticated,
}

class OnboardingFlow extends StatefulWidget {
  const OnboardingFlow({
    super.key,
    required this.isAuthenticated,
    required this.onComplete,
    this.location,
    this.permissions,
  });

  final bool isAuthenticated;
  final LocationCapability? location;
  final PermissionGateway? permissions;
  final Future<void> Function(OnboardingExit exit) onComplete;

  @override
  State<OnboardingFlow> createState() => _OnboardingFlowState();
}

class _OnboardingFlowState extends State<OnboardingFlow> {
  static const _pages = <({String title, String body, IconData icon})>[
    (title: 'Makolo marche pour vous.', body: 'Découvrez des possibilités, préparez ce qui peut l’être et suivez vos actions réelles.', icon: Icons.explore_outlined),
    (title: 'Préparer Makolo', body: 'Choisissez les autorisations à activer.', icon: Icons.tune_rounded),
    (title: 'Tout commence par une découverte.', body: 'Événements, formations, voyages, services et opportunités : explorez librement.', icon: Icons.arrow_forward_rounded),
  ];

  final Map<MakoloPermission, bool> _choices = {
    MakoloPermission.locationWhenInUse: false,
    MakoloPermission.notifications: false,
    MakoloPermission.camera: false,
    MakoloPermission.microphone: false,
  };
  bool _requesting = false;

  Future<void> _applyPermissions() async {
    if (_requesting) return;
    setState(() => _requesting = true);
    try {
      for (final entry in _choices.entries) {
        if (!entry.value) continue;
        if (entry.key == MakoloPermission.locationWhenInUse) {
          final result = await widget.location?.current(
            accuracy: MakoloLocationAccuracy.low,
          );
          DiscoveryLocationContext.update(result?.fix);
        } else {
          await widget.permissions?.requestWhenNeeded(entry.key);
        }
      }
    } finally {
      if (mounted) setState(() => _requesting = false);
    }
  }

  final PageController _controller = PageController();
  int _page = 0;

  bool get _isLastPage => _page == _pages.length - 1;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _next() async {
    if (_isLastPage) {
      await widget.onComplete(
        widget.isAuthenticated
            ? OnboardingExit.continueAuthenticated
            : OnboardingExit.continueGuest,
      );
      return;
    }

    if (_page == 1) await _applyPermissions();
    if (!mounted) return;
    await _controller.nextPage(
      duration: MakoloMotion.medium,
      curve: Curves.easeOutCubic,
    );
  }

  @override
  Widget build(BuildContext context) {
    var primaryLabel = 'Continuer';
    if (_isLastPage) {
      primaryLabel = widget.isAuthenticated
          ? 'Ouvrir Makolo'
          : 'Découvrir';
    }

    return Scaffold(
      body: SafeArea(
        child: Semantics(
          container: true,
          label: 'Bienvenue dans Makolo',
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              MakoloSpacing.xl,
              MakoloSpacing.lg,
              MakoloSpacing.xl,
              MakoloSpacing.xl,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Align(
                  alignment: Alignment.centerLeft,
                  child: MakoloMark(size: 52),
                ),
                const SizedBox(height: MakoloSpacing.lg),
                Expanded(
                  child: PageView.builder(
                    key: const Key('onboarding-pages'),
                    controller: _controller,
                    itemCount: _pages.length,
                    onPageChanged: (value) => setState(() => _page = value),
                    itemBuilder: (context, index) {
                      final item = _pages[index];
                      return SingleChildScrollView(
                        child: Padding(
                          padding: const EdgeInsets.only(
                            top: MakoloSpacing.xl,
                            bottom: MakoloSpacing.lg,
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                item.icon,
                                size: 40,
                                color: Theme.of(context).colorScheme.primary,
                              ),
                              const SizedBox(height: MakoloSpacing.lg),
                              Text(
                                item.title,
                                style: Theme.of(context).textTheme.headlineSmall
                                    ?.copyWith(fontSize: 34, height: 1.12),
                              ),
                              const SizedBox(height: MakoloSpacing.lg),
                              Text(
                                item.body,
                                style: Theme.of(context).textTheme.bodyLarge,
                              ),
                              if (index == 1) ...[
                                const SizedBox(height: MakoloSpacing.lg),
                                for (final choice in <({MakoloPermission permission, String label, IconData icon})>[
                                  (permission: MakoloPermission.locationWhenInUse, label: 'Localisation', icon: Icons.location_on_outlined),
                                  (permission: MakoloPermission.notifications, label: 'Notifications', icon: Icons.notifications_none_rounded),
                                  (permission: MakoloPermission.camera, label: 'Appareil photo', icon: Icons.camera_alt_outlined),
                                  (permission: MakoloPermission.microphone, label: 'Microphone', icon: Icons.mic_none_outlined),
                                ])
                                  CheckboxListTile(
                                    dense: true,
                                    contentPadding: EdgeInsets.zero,
                                    secondary: Icon(choice.icon),
                                    title: Text(choice.label),
                                    value: _choices[choice.permission] ?? false,
                                    onChanged: _requesting ? null : (value) => setState(() {
                                      _choices[choice.permission] = value ?? false;
                                    }),
                                  ),
                              ],
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
                Row(
                  children: [
                    for (var index = 0; index < _pages.length; index++)
                      Padding(
                        padding: const EdgeInsets.only(right: MakoloSpacing.xs),
                        child: AnimatedContainer(
                          duration: MakoloMotion.short,
                          width: index == _page ? 24 : 8,
                          height: 8,
                          decoration: BoxDecoration(
                            color: index == _page
                                ? Theme.of(context).colorScheme.primary
                                : Theme.of(context).colorScheme.outlineVariant,
                            borderRadius: BorderRadius.circular(999),
                          ),
                        ),
                      ),
                    const Spacer(),
                    Text(
                      '${_page + 1}/${_pages.length}',
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                  ],
                ),
                const SizedBox(height: MakoloSpacing.lg),
                FilledButton(
                  key: const Key('onboarding-primary'),
                  onPressed: _requesting ? null : _next,
                  child: Text(primaryLabel),
                ),
                if (!widget.isAuthenticated && _isLastPage) ...[
                  const SizedBox(height: MakoloSpacing.md),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () =>
                              widget.onComplete(OnboardingExit.signIn),
                          child: const Text('J’ai un compte'),
                        ),
                      ),
                      const SizedBox(width: MakoloSpacing.sm),
                      Expanded(
                        child: TextButton(
                          onPressed: () =>
                              widget.onComplete(OnboardingExit.createAccount),
                          child: const Text('Créer un compte'),
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
