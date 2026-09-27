import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../app/session_recovery.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';
import 'auth_entry_frame.dart';
import 'forgot_password_screen.dart';
import 'signup_screen.dart';

enum _EntryMode { login, signup, forgot }

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key, required this.runtime});

  final AppRuntime runtime;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _passwordFocus = FocusNode();

  _EntryMode _mode = _EntryMode.login;
  bool _busy = false;
  bool _showPassword = false;
  String? _error;
  String? _notice;

  @override
  void initState() {
    super.initState();
    if (widget.runtime.recovery.entryReason == EntryReason.sessionExpired) {
      _notice = 'Reconnectez-vous pour continuer.';
    } else if (widget.runtime.recovery.entryReason ==
        EntryReason.accountSwitch) {
      _notice = 'Connectez-vous avec le compte que vous souhaitez utiliser.';
    }
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  void _backToLogin(String email, {String? notice}) {
    setState(() {
      _mode = _EntryMode.login;
      if (email.isNotEmpty) _email.text = email;
      _password.clear();
      _error = null;
      _notice = notice;
    });
  }

  Future<void> _login() async {
    if (_busy) return;
    final email = _email.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      setState(() => _error = 'Indiquez une adresse e-mail valide.');
      return;
    }
    if (_password.text.isEmpty) {
      setState(() => _error = 'Indiquez votre mot de passe.');
      return;
    }

    final api = widget.runtime.api;
    if (api == null) {
      setState(() {
        _error = 'La connexion est indisponible sur cette installation pour le moment.';
      });
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthRepository(
        api,
        widget.runtime.tokens,
      ).login(email: email, password: _password.text);
      TextInput.finishAutofillContext();
      ref.invalidate(appRuntimeProvider);
    } on MakoloApiError catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.statusCode == 400 || error.statusCode == 401
            ? 'Adresse e-mail ou mot de passe incorrect.'
            : error.statusCode == 429
            ? 'Trop de tentatives pour le moment. Réessayez un peu plus tard.'
            : 'Connexion impossible pour le moment. Réessayez dans un instant.';
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _error = 'Connexion impossible pour le moment. Votre saisie reste disponible.';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_mode == _EntryMode.signup) {
      return SignupScreen(
        runtime: widget.runtime,
        onBackToLogin: _backToLogin,
        onRegistered: (email) => _backToLogin(
          email,
          notice: 'Votre compte est prêt. Connectez-vous pour continuer.',
        ),
      );
    }
    if (_mode == _EntryMode.forgot) {
      return ForgotPasswordScreen(
        runtime: widget.runtime,
        initialEmail: _email.text.trim(),
        onBackToLogin: (email) => _backToLogin(email),
      );
    }

    return AuthEntryFrame(
      title: 'Connectez-vous à Makolo',
      subtitle: 'Makolo marche avec vous.',
      child: AutofillGroup(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_notice != null) ...[
              Semantics(
                liveRegion: true,
                child: Container(
                  key: const Key('login-notice'),
                  padding: const EdgeInsets.all(MakoloSpacing.md),
                  decoration: BoxDecoration(
                    color: MakoloColors.indigo.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(MakoloRadii.small),
                  ),
                  child: Text(_notice!),
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
            ],
            TextField(
              key: const Key('login-email'),
              controller: _email,
              enabled: !_busy,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [
                AutofillHints.username,
                AutofillHints.email,
              ],
              textInputAction: TextInputAction.next,
              onEditingComplete: () => _passwordFocus.requestFocus(),
              decoration: const InputDecoration(
                labelText: 'Adresse e-mail',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: MakoloSpacing.md),
            TextField(
              key: const Key('login-password'),
              controller: _password,
              focusNode: _passwordFocus,
              enabled: !_busy,
              obscureText: !_showPassword,
              autofillHints: const [AutofillHints.password],
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _login(),
              decoration: InputDecoration(
                labelText: 'Mot de passe',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  key: const Key('login-password-toggle'),
                  tooltip: _showPassword
                      ? 'Masquer le mot de passe'
                      : 'Afficher le mot de passe',
                  onPressed: _busy
                      ? null
                      : () => setState(() => _showPassword = !_showPassword),
                  icon: Icon(
                    _showPassword ? Icons.visibility_off : Icons.visibility,
                  ),
                ),
              ),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                key: const Key('forgot-password-link'),
                onPressed: _busy
                    ? null
                    : () => setState(() {
                        _mode = _EntryMode.forgot;
                        _error = null;
                        _notice = null;
                      }),
                child: const Text('Mot de passe oublié ?'),
              ),
            ),
            if (_error != null) ...[
              Semantics(
                liveRegion: true,
                child: Text(
                  _error!,
                  key: const Key('login-error'),
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
              const SizedBox(height: MakoloSpacing.md),
            ],
            FilledButton(
              key: const Key('login-submit'),
              onPressed: _busy ? null : _login,
              child: Text(_busy ? 'Connexion…' : 'Se connecter'),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            TextButton(
              key: const Key('create-account-link'),
              onPressed: _busy
                  ? null
                  : () => setState(() {
                      _mode = _EntryMode.signup;
                      _error = null;
                      _notice = null;
                    }),
              child: const Text('Créer un compte'),
            ),
          ],
        ),
      ),
    );
  }
}
