import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';

/// Shared purple identity for login, signup and account recovery.
class AuthEntryFrame extends StatelessWidget {
  const AuthEntryFrame({
    super.key,
    required this.title,
    this.subtitle,
    required this.child,
    this.onBack,
    this.footer = '',
  });

  final String title;
  final String? subtitle;
  final Widget child;
  final VoidCallback? onBack;
  final String footer;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
    final compact = MediaQuery.sizeOf(context).height < 700 || keyboardOpen;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        statusBarBrightness: Brightness.dark,
        systemNavigationBarColor: MakoloColors.indigo,
        systemNavigationBarIconBrightness: Brightness.light,
      ),
      child: Scaffold(
        backgroundColor: MakoloColors.indigo,
        resizeToAvoidBottomInset: true,
        body: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              const horizontal = MakoloSpacing.lg;
              final vertical = compact ? MakoloSpacing.sm : MakoloSpacing.lg;

              return SingleChildScrollView(
                keyboardDismissBehavior:
                    ScrollViewKeyboardDismissBehavior.onDrag,
                padding: EdgeInsets.symmetric(
                  horizontal: horizontal,
                  vertical: vertical,
                ),
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: constraints.maxHeight > vertical * 2
                        ? constraints.maxHeight - vertical * 2
                        : 0.0,
                  ),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 440),
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
                                icon: const Icon(Icons.arrow_back_rounded),
                              ),
                            ),
                          SizedBox(
                            height: compact
                                ? MakoloSpacing.xs
                                : MakoloSpacing.md,
                          ),
                          Center(
                            child: MakoloMark(
                              size: compact ? 52 : 64,
                              white: true,
                            ),
                          ),
                          SizedBox(
                            height: compact
                                ? MakoloSpacing.md
                                : MakoloSpacing.lg,
                          ),
                          Text(
                            title,
                            textAlign: TextAlign.center,
                            style: textTheme.headlineSmall?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                              height: 1.18,
                            ),
                          ),
                          if (subtitle != null &&
                              subtitle!.trim().isNotEmpty) ...[
                            const SizedBox(height: MakoloSpacing.sm),
                            Text(
                              subtitle!,
                              textAlign: TextAlign.center,
                              style: textTheme.bodyLarge?.copyWith(
                                color: Colors.white.withValues(alpha: 0.90),
                                height: 1.4,
                              ),
                            ),
                          ],
                          SizedBox(
                            height: compact
                                ? MakoloSpacing.lg
                                : MakoloSpacing.xl,
                          ),
                          child,
                          if (!keyboardOpen && footer.isNotEmpty) ...[
                            const SizedBox(height: MakoloSpacing.xl),
                            Text(
                              footer,
                              textAlign: TextAlign.center,
                              style: textTheme.bodySmall?.copyWith(
                                color: Colors.white.withValues(alpha: 0.74),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                          const SizedBox(height: MakoloSpacing.md),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
