import 'package:flutter/material.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

class AuthEntryFrame extends StatelessWidget {
  const AuthEntryFrame({
    super.key,
    required this.title,
    required this.subtitle,
    required this.child,
    this.onBack,
    this.footer = 'Avance, tout est déjà prêt.',
  });

  final String title;
  final String subtitle;
  final Widget child;
  final VoidCallback? onBack;
  final String footer;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      backgroundColor: MakoloColors.indigo,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            padding: const EdgeInsets.symmetric(
              horizontal: MakoloSpacing.lg,
              vertical: MakoloSpacing.lg,
            ),
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minHeight: constraints.maxHeight - (MakoloSpacing.lg * 2),
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 480),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (onBack != null)
                        Align(
                          alignment: Alignment.centerLeft,
                          child: IconButton(
                            tooltip: 'Retour',
                            onPressed: onBack,
                            color: Colors.white,
                            icon: const Icon(Icons.arrow_back),
                          ),
                        ),
                      const SizedBox(height: MakoloSpacing.sm),
                      const Center(child: MakoloMark(size: 72, white: true)),
                      const SizedBox(height: MakoloSpacing.lg),
                      Text(
                        title,
                        textAlign: TextAlign.center,
                        style: textTheme.headlineSmall?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: MakoloSpacing.sm),
                      Text(
                        subtitle,
                        textAlign: TextAlign.center,
                        style: textTheme.bodyLarge?.copyWith(
                          color: Colors.white.withValues(alpha: 0.88),
                          height: 1.45,
                        ),
                      ),
                      const SizedBox(height: MakoloSpacing.xl),
                      DecoratedBox(
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(
                            MakoloRadii.large,
                          ),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(MakoloSpacing.lg),
                          child: child,
                        ),
                      ),
                      const SizedBox(height: MakoloSpacing.lg),
                      Text(
                        footer,
                        textAlign: TextAlign.center,
                        style: textTheme.bodyMedium?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
