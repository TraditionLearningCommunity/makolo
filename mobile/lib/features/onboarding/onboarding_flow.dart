import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';
import '../../platform/location/location_capability.dart';
import '../../platform/location/location_service.dart';
import '../../platform/location/discovery_location_context.dart';

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
  });

  final bool isAuthenticated;
  final LocationCapability? location;
  final Future<void> Function(OnboardingExit exit) onComplete;

  @override
  State<OnboardingFlow> createState() => _OnboardingFlowState();
}

class _OnboardingFlowState extends State<OnboardingFlow> {
  static const _pages = <({String title, String body, IconData icon})>[
    (
      title: 'Makolo marche pour vous.',
      body: 'Découvrez des opportunités, simplifiez vos démarches et avancez dans ce qui compte pour vous.',
      icon: Icons.explore_outlined,
    ),
    (
      title: 'Découvrez ce qui vous entoure.',
      body: 'Avec votre localisation, Makolo peut vous montrer les activités, services et opportunités près de vous.',
      icon: Icons.location_on_outlined,
    ),
    (
      title: 'Tout commence par une découverte.',
      body: 'Explorez des événements, des formations, des voyages, des services et bien d’autres opportunités.',
      icon: Icons.arrow_forward_rounded,
    ),
  ];

  bool _requesting = false;
  bool _locationGranted = false;
  String? _locationFeedback;

  Future<void> _advance() async {
    if (!mounted) return;
    await _controller.nextPage(
      duration: MakoloMotion.medium,
      curve: Curves.easeOutCubic,
    );
  }

  Future<void> _skipLocation() async {
    if (!_locationGranted) DiscoveryLocationContext.update(null);
    await _advance();
  }

  Future<void> _activateLocation() async {
    if (_requesting || _page != 1) return;
    if (_locationGranted || DiscoveryLocationContext.current != null) {
      setState(() => _locationGranted = true);
      await _advance();
      return;
    }
    setState(() {
      _requesting = true;
      _locationFeedback = null;
    });
    try {
      final location = widget.location;
      if (location == null) {
        DiscoveryLocationContext.update(null);
        if (mounted) {
          setState(
            () => _locationFeedback =
                'La localisation n’a pas pu démarrer. Réessayez ou passez.',
          );
        }
        return;
      }
      final result = await location.current(
        accuracy: MakoloLocationAccuracy.low,
      );
      if (!mounted) return;
      DiscoveryLocationContext.update(
        result.status == LocationCapabilityStatus.ready ? result.fix : null,
      );
      if (result.status == LocationCapabilityStatus.ready &&
          result.fix != null) {
        setState(() => _locationGranted = true);
        await _advance();
        return;
      }
      setState(() {
        _locationFeedback = switch (result.status) {
          LocationCapabilityStatus.settingsRequired => 'La localisation est bloquée dans les réglages Android. Vous pouvez continuer sans elle.',
          LocationCapabilityStatus.serviceUnavailable => 'Le service de localisation est désactivé. Vous pouvez continuer sans lui.',
          LocationCapabilityStatus.permissionDenied ||
          LocationCapabilityStatus.restricted => 'La localisation n’est pas autorisée. Vous pouvez continuer sans elle.',
          _ => 'Votre position n’a pas pu être obtenue. Vous pouvez continuer sans elle.',
        };
      });
    } on Object {
      DiscoveryLocationContext.update(null);
      if (mounted) {
        setState(
          () => _locationFeedback = 'La localisation est indisponible. Vous pouvez continuer sans elle.',
        );
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

    await _advance();
  }

  @override
  Widget build(BuildContext context) {
    var primaryLabel = 'Continuer';
    if (_isLastPage) {
      primaryLabel = widget.isAuthenticated
          ? 'Ouvrir Makolo'
          : 'Entrer dans Makolo';
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
                                if (_locationFeedback != null) ...[
                                  const SizedBox(height: MakoloSpacing.md),
                                  Text(
                                    _locationFeedback!,
                                    key: const Key(
                                      'onboarding-location-feedback',
                                    ),
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodyMedium,
                                  ),
                                ],
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
                  onPressed: _requesting
                      ? null
                      : _page == 1
                      ? (_locationGranted ? _advance : _activateLocation)
                      : _next,
                  child: Text(
                    _page == 1
                        ? (_locationGranted
                              ? 'Continuer'
                              : 'Activer la localisation')
                        : primaryLabel,
                  ),
                ),
                if (_page == 1 && !_locationGranted) ...[
                  const SizedBox(height: MakoloSpacing.sm),
                  TextButton(
                    key: const Key('onboarding-location-skip'),
                    onPressed: _requesting ? null : _skipLocation,
                    style: TextButton.styleFrom(
                      foregroundColor: Theme.of(context).colorScheme.onSurface,
                    ),
                    child: const Text('Passer'),
                  ),
                ],
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
