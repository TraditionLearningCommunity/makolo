import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../app/session_recovery.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_theme.dart';
import '../../network/api_error.dart';
import 'account_chooser_screen.dart';
import 'auth_components.dart';
import 'auth_entry_frame.dart';
import 'forgot_password_screen.dart';
import 'signup_screen.dart';

enum _EntryMode { login, signup, accounts }

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({
    super.key,
    required this.runtime,
    this.initialEmail,
    this.startWithAccounts = false,
  });

  final AppRuntime runtime;
  final String? initialEmail;
  final bool startWithAccounts;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _passwordFocus = FocusNode();

  late _EntryMode _mode;
  bool _busy = false;
  bool _showPassword = false;
  bool _rememberOnDevice = false;
  String? _error;
  String? _notice;
  Timer? _draftTimer;

  @override
  void initState() {
    super.initState();
    _mode = widget.startWithAccounts ? _EntryMode.accounts : _EntryMode.login;
    final initialEmail = widget.initialEmail?.trim() ?? '';
    if (initialEmail.isNotEmpty) {
      _email.text = initialEmail;
    } else {
      unawaited(_restoreDraft());
    }
    _email.addListener(_scheduleDraftSave);

    if (widget.runtime.recovery.entryReason == EntryReason.sessionExpired) {
      _notice = 'Reconnectez-vous pour continuer.';
    } else if (widget.runtime.recovery.entryReason == EntryReason.protectedAction) {
      _notice = 'Connectez-vous pour continuer.';
    }
  }

  Future<void> _restoreDraft() async {
    final draft = await widget.runtime.interactions?.read('login');
    if (!mounted || _email.text.isNotEmpty) return;
    final email = draft?['email'];
    if (email is String) _email.text = email;
  }

  void _scheduleDraftSave() {
    _draftTimer?.cancel();
    _draftTimer = Timer(const Duration(milliseconds: 250), () {
      unawaited(
        widget.runtime.interactions?.save('login', {
          'email': _email.text.trim(),
        }) ?? Future<void>.value(),
      );
    });
  }

  @override
  void dispose() {
    _draftTimer?.cancel();
    _email.dispose();
    _password.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  void _showLogin({String email = ''}) {
    setState(() {
      _mode = _EntryMode.login;
      if (email.isNotEmpty) _email.text = email;
      _password.clear();
      _error = null;
      _notice = null;
    });
  }

  String? _validateEmail(String? value) {
    final email = value?.trim() ?? '';
    if (email.isEmpty || !email.contains('@')) {
      return 'Indiquez une adresse e-mail valide.';
    }
    return null;
  }

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) {
      return 'Indiquez votre mot de passe.';
    }
    return null;
  }

  Future<void> _login() async {
    if (_busy || !_formKey.currentState!.validate()) return;
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
      await AuthRepository(api, widget.runtime.tokens).login(
        email: _email.text.trim(),
        password: _password.text,
        rememberOnDevice: _rememberOnDevice,
      );
      TextInput.finishAutofillContext();
      await widget.runtime.interactions?.clear('login');
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

  Future<void> _forgotPassword() async {
    final email = await showForgotPasswordDialog(
      context,
      runtime: widget.runtime,
      initialEmail: _email.text.trim(),
    );
    if (!mounted || email == null || email.isEmpty) return;
    _email.text = email;
  }

  @override
  Widget build(BuildContext context) {
    if (_mode == _EntryMode.accounts) {
      return DeviceAccountsScreen(
        runtime: widget.runtime,
        onUsePassword: (email) => _showLogin(email: email),
        onAddAccount: _showLogin,
      );
    }

    if (_mode == _EntryMode.signup) {
      return SignupScreen(
        runtime: widget.runtime,
        onBackToLogin: (email) => _showLogin(email: email),
        onAuthenticated: () => ref.invalidate(appRuntimeProvider),
      );
    }

    return AuthEntryFrame(
      title: 'Connectez-vous à Makolo',
      subtitle: 'Makolo marche avec vous.',
      child: AutofillGroup(
        child: Form(
          key: _formKey,
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
                      color: Colors.white.withValues(alpha: 0.14),
                      borderRadius: BorderRadius.circular(MakoloRadii.medium),
                    ),
                    child: Text(
                      _notice!,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: MakoloSpacing.md),
              ],
              MakoloAuthField(
                fieldKey: const Key('login-email'),
                controller: _email,
                enabled: !_busy,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [
                  AutofillHints.username,
                  AutofillHints.email,
                ],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.alternate_email,
                validator: _validateEmail,
                onEditingComplete: () => _passwordFocus.requestFocus(),
                label: 'Adresse e-mail',
              ),
              const SizedBox(height: MakoloSpacing.md),
              MakoloAuthField(
                fieldKey: const Key('login-password'),
                controller: _password,
                focusNode: _passwordFocus,
                enabled: !_busy,
                obscureText: !_showPassword,
                autofillHints: const [AutofillHints.password],
                textInputAction: TextInputAction.done,
                prefixIcon: Icons.lock_outline,
                validator: _validatePassword,
                onFieldSubmitted: (_) => _login(),
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
                    color: MakoloColors.deep,
                  ),
                ),
                label: 'Mot de passe',
              ),
              Align(
                alignment: Alignment.centerRight,
                child: MakoloAuthTextAction(
                  label: 'Mot de passe oublié ?',
                  buttonKey: const Key('forgot-password-link'),
                  onPressed: _busy ? null : _forgotPassword,
                  underline: true,
                ),
              ),
              MakoloQuickAccessChoice(
                value: _rememberOnDevice,
                onChanged: _busy
                    ? null
                    : (value) => setState(() => _rememberOnDevice = value),
              ),
              if (_error != null) ...[
                const SizedBox(height: MakoloSpacing.md),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    key: const Key('login-error'),
                    style: const TextStyle(
                      color: Color(0xFFFFDAD6),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
              const SizedBox(height: MakoloSpacing.lg),
              MakoloAuthPrimaryButton(
                buttonKey: const Key('login-submit'),
                label: 'Se connecter',
                busy: _busy,
                onPressed: _login,
              ),
              const SizedBox(height: MakoloSpacing.sm),
              MakoloAuthSecondaryButton(
                label: 'Créer un compte',
                buttonKey: const Key('create-account-link'),
                onPressed: _busy
                    ? null
                    : () => setState(() {
                        _mode = _EntryMode.signup;
                        _error = null;
                        _notice = null;
                      }),
              ),
              FutureBuilder(
                future: widget.runtime.tokens.listAccounts(),
                builder: (context, snapshot) {
                  final hasAccounts =
                      snapshot.data != null && snapshot.data!.isNotEmpty;
                  if (!hasAccounts) return const SizedBox.shrink();
                  return MakoloAuthTextAction(
                    label: 'Utiliser un autre compte de cet appareil',
                    onPressed: _busy
                        ? null
                        : () => setState(() => _mode = _EntryMode.accounts),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
