import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

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
  });

  final bool isAuthenticated;
  final Future<void> Function(OnboardingExit exit) onComplete;

  @override
  State<OnboardingFlow> createState() => _OnboardingFlowState();
}

class _OnboardingFlowState extends State<OnboardingFlow> {
  static const _pages = <({String title, String body, IconData icon})>[
    (
      title: 'Découvrez ce qui compte vraiment.',
      body:
          'Explorez des possibilités réelles sans transformer Makolo en simple fil à parcourir.',
      icon: Icons.explore_outlined,
    ),
    (
      title: 'Préparez ce qui peut l’être.',
      body:
          'Rassemblez le contexte utile avant le moment d’agir et voyez clairement ce qui reste à faire.',
      icon: Icons.inventory_2_outlined,
    ),
    (
      title: 'Avancez dans l’action réelle.',
      body:
          'Retrouvez vos démarches, vos prochaines actions et la continuité nécessaire pour aller jusqu’au bout.',
      icon: Icons.arrow_forward_rounded,
    ),
  ];

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

    await _controller.nextPage(
      duration: MakoloMotion.medium,
      curve: Curves.easeOutCubic,
    );
  }

  @override
  Widget build(BuildContext context) {
    final page = _pages[_page];

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
                  onPressed: _next,
                  child: Text(
                    _isLastPage
                        ? widget.isAuthenticated
                            ? 'Ouvrir Makolo'
                            : 'Découvrir Makolo'
                        : 'Continuer',
                  ),
                ),
                if (!widget.isAuthenticated && _isLastPage) ...[
                  const SizedBox(height: MakoloSpacing.md),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () =>
                              widget.onComplete(OnboardingExit.signIn),
                          child: const Text('Se connecter'),
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
