import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_mark.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final api = widget.runtime.api;
    if (api == null) return;
    final auth = AuthRepository(api, widget.runtime.tokens);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await auth.login(email: _email.text.trim(), password: _password.text);
      ref.invalidate(appRuntimeProvider);
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.statusCode == 401 || error.statusCode == 400
            ? 'Adresse e-mail ou mot de passe incorrect.'
            : 'Connexion impossible pour le moment. Réessayez dans un instant.';
      });
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'Connexion impossible pour le moment. Votre saisie reste disponible.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(MakoloSpacing.xl),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Center(child: MakoloMark(size: 72)),
                    const SizedBox(height: MakoloSpacing.lg),
                    Text(
                      'Makolo',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: MakoloSpacing.sm),
                    Text(
                      widget.runtime.apiConfigured
                          ? 'Connectez-vous pour retrouver ce qui est disponible pour vous sur cet appareil.'
                          : 'Une première connexion est nécessaire. Configurez un environnement Makolo autorisé pour continuer.',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: MakoloSpacing.xl),
                    if (widget.runtime.apiConfigured) ...[
                      TextField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.email],
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          labelText: 'Adresse e-mail',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: MakoloSpacing.md),
                      TextField(
                        controller: _password,
                        obscureText: true,
                        autofillHints: const [AutofillHints.password],
                        onSubmitted: (_) => _busy ? null : _login(),
                        decoration: const InputDecoration(
                          labelText: 'Mot de passe',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: MakoloSpacing.md),
                        Semantics(
                          liveRegion: true,
                          child: Text(
                            _error!,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                            ),
                          ),
                        ),
                      ],
                      const SizedBox(height: MakoloSpacing.lg),
                      FilledButton(
                        onPressed: _busy ? null : _login,
                        child: Text(_busy ? 'Connexion…' : 'Continuer'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
