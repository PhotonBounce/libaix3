# ProGuard rules for OpsBrief - add rules if needed for R8/minification

# Capacitor core keep rules
-keep public class * extends com.getcapacitor.Plugin { *; }
-keep public class com.getcapacitor.** { *; }
-dontwarn com.getcapacitor.**

# Keep BridgeActivity and related classes
-keep public class com.getcapacitor.BridgeActivity { *; }
-keep public class com.getcapacitor.CapacitorWebView { *; }
