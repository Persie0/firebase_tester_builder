import 'dart:async';

import 'package:flutter/material.dart';
import 'package:purchases_flutter/purchases_flutter.dart';

const _testStoreKey = String.fromEnvironment('REVENUECAT_TEST_STORE_API_KEY');
const _entitlementId = String.fromEnvironment('REVENUECAT_CI_ENTITLEMENT');
const _appUserId = String.fromEnvironment('REVENUECAT_CI_USER_ID');

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const RevenueCatCiApp());
}

class RevenueCatCiApp extends StatelessWidget {
  const RevenueCatCiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: RevenueCatCiScreen(),
    );
  }
}

class RevenueCatCiScreen extends StatefulWidget {
  const RevenueCatCiScreen({super.key});

  @override
  State<RevenueCatCiScreen> createState() => _RevenueCatCiScreenState();
}

class _RevenueCatCiScreenState extends State<RevenueCatCiScreen> {
  String _status = 'REVENUECAT_CI_BOOTING';
  String _details = '';
  bool _ready = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    unawaited(_initialize());
  }

  bool _hasEntitlement(CustomerInfo info) {
    return info.entitlements.active.containsKey(_entitlementId);
  }

  Future<void> _initialize() async {
    try {
      if (!_testStoreKey.startsWith('test_')) {
        throw StateError(
          'CI refuses to run unless REVENUECAT_TEST_STORE_API_KEY starts with test_.',
        );
      }
      if (_entitlementId.isEmpty) {
        throw StateError('REVENUECAT_CI_ENTITLEMENT is empty.');
      }
      if (_appUserId.isEmpty) {
        throw StateError('REVENUECAT_CI_USER_ID is empty.');
      }

      await Purchases.setLogLevel(LogLevel.debug);
      if (!await Purchases.isConfigured) {
        await Purchases.configure(
          PurchasesConfiguration(_testStoreKey)..appUserID = _appUserId,
        );
      }

      await Purchases.invalidateCustomerInfoCache();
      final info = await Purchases.getCustomerInfo();
      if (!mounted) return;
      setState(() {
        _ready = true;
        _status = _hasEntitlement(info)
            ? 'PERSISTED_AFTER_RESTART'
            : 'REVENUECAT_CI_READY';
        _details = 'user=$_appUserId entitlement=$_entitlementId';
      });
    } catch (error, stackTrace) {
      _fail(error, stackTrace);
    }
  }

  Future<Package> _packageToPurchase() async {
    final offerings = await Purchases.getOfferings();
    final current = offerings.current;
    if (current != null && current.availablePackages.isNotEmpty) {
      return current.availablePackages.first;
    }
    for (final offering in offerings.all.values) {
      if (offering.availablePackages.isNotEmpty) {
        return offering.availablePackages.first;
      }
    }
    throw StateError(
      'No RevenueCat Test Store package is attached to any offering.',
    );
  }

  Future<void> _purchaseAndVerify() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _status = 'PURCHASE_STARTING';
      _details = '';
    });

    try {
      final package = await _packageToPurchase();
      if (!mounted) return;
      setState(() {
        _status = 'PURCHASE_DIALOG_OPENING';
        _details = package.storeProduct.identifier;
      });

      final result = await Purchases.purchasePackage(package);
      if (!_hasEntitlement(result.customerInfo)) {
        throw StateError(
          'Purchase completed but entitlement "$_entitlementId" was not active.',
        );
      }

      // Do not trust the purchase response or local RevenueCat cache. Force a
      // fresh CustomerInfo read from RevenueCat and verify the entitlement again.
      await Purchases.invalidateCustomerInfoCache();
      final freshInfo = await Purchases.getCustomerInfo();
      if (!_hasEntitlement(freshInfo)) {
        throw StateError(
          'Entitlement disappeared after invalidating CustomerInfo cache.',
        );
      }

      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = 'PURCHASE_REMOTE_ACTIVE';
        _details = 'Restart the app now; the same CI App User ID must stay Pro.';
      });
    } catch (error, stackTrace) {
      _fail(error, stackTrace);
    }
  }

  Future<void> _restoreAndVerify() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _status = 'RESTORE_STARTING';
      _details = '';
    });
    try {
      final info = await Purchases.restorePurchases();
      if (!_hasEntitlement(info)) {
        throw StateError(
          'restorePurchases() completed without entitlement "$_entitlementId".',
        );
      }
      await Purchases.invalidateCustomerInfoCache();
      final freshInfo = await Purchases.getCustomerInfo();
      if (!_hasEntitlement(freshInfo)) {
        throw StateError('Restored entitlement did not survive a fresh fetch.');
      }
      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = 'ALL_REVENUECAT_CHECKS_PASSED';
        _details = 'purchase + fresh fetch + restart + restore are active';
      });
    } catch (error, stackTrace) {
      _fail(error, stackTrace);
    }
  }

  void _fail(Object error, StackTrace stackTrace) {
    debugPrint('RevenueCat CI failure: $error\n$stackTrace');
    if (!mounted) return;
    setState(() {
      _busy = false;
      _status = 'REVENUECAT_CI_FAILED';
      _details = error.toString();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('RevenueCat CI')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 680),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SelectableText(
                    _status,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 12),
                  SelectableText(_details, textAlign: TextAlign.center),
                  const SizedBox(height: 28),
                  FilledButton(
                    onPressed: _ready && !_busy ? _purchaseAndVerify : null,
                    child: const Text('Start RevenueCat CI purchase'),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton(
                    onPressed: _ready && !_busy ? _restoreAndVerify : null,
                    child: const Text('Restore and verify purchase'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
