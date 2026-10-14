import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../app/session_recovery.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_theme.dart';
import 'auth_error_messages.dart';
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
  final _identifier = TextEditingController();
  final _password = TextEditingController();
  final _passwordFocus = FocusNode();

  late _EntryMode _mode;
  late Future<bool> _hasStoredAccounts;
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
    _hasStoredAccounts = _checkStoredAccounts();
    final initial = widget.initialEmail?.trim() ?? '';
    if (initial.isNotEmpty) {
      _identifier.text = initial;
    } else {
      unawaited(_restoreDraft());
    }
    _identifier.addListener(_scheduleDraftSave);

    final reason = widget.runtime.recovery.entryReason;
    if (reason == EntryReason.sessionExpired) {
      _notice = 'Votre session a expiré. Reconnectez-vous pour continuer.';
    } else if (reason == EntryReason.protectedIntent ||
        reason == EntryReason.protectedAction) {
      _notice = 'Connectez-vous pour poursuivre votre action.';
    }
  }

  Future<bool> _checkStoredAccounts() async {
    try {
      return (await widget.runtime.tokens.listAccounts()).isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<void> _restoreDraft() async {
    try {
      final draft = await widget.runtime.interactions?.read('login');
      if (!mounted || _identifier.text.isNotEmpty) return;
      final value = draft?['identifier'] ?? draft?['email'];
      if (value is String) _identifier.text = value.trim();
    } catch (_) {
      // Draft persistence is optional; it cannot prevent login.
    }
  }

  void _scheduleDraftSave() {
    _draftTimer?.cancel();
    if (_busy) return;
    _draftTimer = Timer(const Duration(milliseconds: 300), () {
      if (mounted) unawaited(_saveDraft());
    });
  }

  Future<void> _saveDraft() async {
    try {
      await widget.runtime.interactions?.save('login', {
        'identifier': _identifier.text.trim(),
      });
    } catch (_) {
      // No password is stored in the draft.
    }
  }

  @override
  void dispose() {
    _draftTimer?.cancel();
    _identifier.dispose();
    _password.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  void _showLogin({String email = ''}) {
    setState(() {
      _mode = _EntryMode.login;
      if (email.isNotEmpty) _identifier.text = email;
      _password.clear();
      _showPassword = false;
      _error = null;
      _notice = null;
    });
  }

  String? _validateIdentifier(String? value) {
    return (value?.trim() ?? '').isEmpty
        ? 'Saisissez votre identifiant Makolo ou votre e-mail.'
        : null;
  }

  String? _validatePassword(String? value) {
    return (value == null || value.isEmpty)
        ? 'Saisissez votre mot de passe.'
        : null;
  }

  String _passwordRecoveryEmail() {
    final value = _identifier.text.trim();
    if (value.startsWith('@') || !value.contains('@')) return '';
    return value;
  }

  Future<void> _login() async {
    if (_busy || !(_formKey.currentState?.validate() ?? false)) return;
    final api = widget.runtime.api;
    if (api == null) {
      setState(() {
        _error =
            'La connexion est indisponible sur cette installation '
            'pour le moment.';
      });
      return;
    }

    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await AuthRepository(api, widget.runtime.tokens).login(
        identifier: _identifier.text.trim(),
        password: _password.text,
        rememberOnDevice: _rememberOnDevice,
      );
      TextInput.finishAutofillContext(shouldSave: true);
      _draftTimer?.cancel();
      try {
        await widget.runtime.interactions?.clear('login');
      } catch (_) {
        // An optional draft cleanup must not undo a valid login.
      }
      if (!mounted) return;
      ref.invalidate(appRuntimeProvider);
    } on Object catch (error) {
      final message = await resolvedLoginErrorMessage(error);
      if (!mounted) return;
      setState(() => _error = message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _forgotPassword() async {
    FocusManager.instance.primaryFocus?.unfocus();
    final email = await showForgotPasswordDialog(
      context,
      runtime: widget.runtime,
      initialEmail: _passwordRecoveryEmail(),
    );
    if (!mounted || email == null || email.isEmpty) return;
    _identifier.text = email;
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
      subtitle: 'Makolo marche pour vous.',
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
                      color: Colors.white.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(MakoloRadii.card),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.25),
                      ),
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
                const SizedBox(height: MakoloSpacing.lg),
              ],
              MakoloAuthField(
                fieldKey: const Key('login-email'),
                label: 'Identifiant Makolo ou adresse e-mail',
                hint: 'Identifiant ou e-mail',
                controller: _identifier,
                enabled: !_busy,
                keyboardType: TextInputType.text,
                autofillHints: const [
                  AutofillHints.username,
                  AutofillHints.email,
                ],
                textInputAction: TextInputAction.next,
                prefixIcon: Icons.alternate_email_rounded,
                validator: _validateIdentifier,
                onChanged: (_) {
                  if (_error != null) setState(() => _error = null);
                },
                onEditingComplete: () => _passwordFocus.requestFocus(),
              ),
              const SizedBox(height: MakoloSpacing.inner),
              MakoloAuthField(
                fieldKey: const Key('login-password'),
                label: 'Mot de passe',
                hint: 'Votre mot de passe',
                controller: _password,
                focusNode: _passwordFocus,
                enabled: !_busy,
                obscureText: !_showPassword,
                autofillHints: const [AutofillHints.password],
                textInputAction: TextInputAction.done,
                prefixIcon: Icons.lock_outline_rounded,
                validator: _validatePassword,
                onChanged: (_) {
                  if (_error != null) setState(() => _error = null);
                },
                onFieldSubmitted: (_) => unawaited(_login()),
                suffixIcon: IconButton(
                  key: const Key('login-password-toggle'),
                  tooltip: _showPassword
                      ? 'Masquer le mot de passe'
                      : 'Afficher le mot de passe',
                  onPressed: _busy
                      ? null
                      : () => setState(() => _showPassword = !_showPassword),
                  icon: Icon(
                    _showPassword
                        ? Icons.visibility_off_outlined
                        : Icons.visibility_outlined,
                    color: MakoloColors.deep,
                  ),
                ),
              ),
              Align(
                alignment: Alignment.centerRight,
                child: MakoloAuthTextAction(
                  label: 'Mot de passe oublié ?',
                  buttonKey: const Key('forgot-password-link'),
                  onPressed: _busy ? null : () => unawaited(_forgotPassword()),
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
                const SizedBox(height: MakoloSpacing.sm),
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    key: const Key('login-error'),
                    style: const TextStyle(
                      color: Color(0xFFFFE5E0),
                      fontWeight: FontWeight.w700,
                      height: 1.45,
                    ),
                  ),
                ),
              ],
              const SizedBox(height: MakoloSpacing.lg),
              MakoloAuthPrimaryButton(
                buttonKey: const Key('login-submit'),
                label: 'Se connecter',
                busy: _busy,
                onPressed: () => unawaited(_login()),
              ),
              const SizedBox(height: MakoloSpacing.sm),
              MakoloAuthSecondaryButton(
                buttonKey: const Key('create-account-link'),
                label: 'Créer un compte',
                onPressed: _busy
                    ? null
                    : () {
                        FocusManager.instance.primaryFocus?.unfocus();
                        setState(() {
                          _mode = _EntryMode.signup;
                          _error = null;
                          _notice = null;
                        });
                      },
              ),
              FutureBuilder<bool>(
                future: _hasStoredAccounts,
                builder: (context, snapshot) {
                  if (snapshot.data != true) return const SizedBox.shrink();
                  return Padding(
                    padding: const EdgeInsets.only(top: MakoloSpacing.sm),
                    child: MakoloAuthTextAction(
                      label: 'Utiliser un autre compte de cet appareil',
                      onPressed: _busy
                          ? null
                          : () {
                              FocusManager.instance.primaryFocus?.unfocus();
                              setState(() => _mode = _EntryMode.accounts);
                            },
                    ),
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
