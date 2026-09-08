<x-guest-layout>
    <div class="mb-8">
        <h2 class="text-2xl font-semibold text-gray-900">Welcome back</h2>
        <p class="mt-1 text-sm text-gray-500">Sign in to your SMSC account.</p>
    </div>

    <!-- Session Status -->
    <x-auth-session-status class="mb-4" :status="session('status')" />

    <form method="POST" action="{{ route('login') }}" class="space-y-5">
        @csrf

        <!-- Email Address -->
        <div>
            <x-input-label for="email" :value="__('Email')" />
            <x-text-input id="email" class="block mt-1 w-full" type="email" name="email" :value="old('email')" required autofocus autocomplete="username" placeholder="you@example.com" />
            <x-input-error :messages="$errors->get('email')" class="mt-2" />
        </div>

        <!-- Password -->
        <div>
            <div class="flex items-center justify-between">
                <x-input-label for="password" :value="__('Password')" />
                @if (Route::has('password.request'))
                    <a class="text-sm text-indigo-600 hover:text-indigo-800" href="{{ route('password.request') }}">
                        {{ __('Forgot password?') }}
                    </a>
                @endif
            </div>

            <x-text-input id="password" class="block mt-1 w-full"
                            type="password"
                            name="password"
                            required autocomplete="current-password" placeholder="••••••••" />

            <x-input-error :messages="$errors->get('password')" class="mt-2" />
        </div>

        <!-- Remember Me -->
        <label for="remember_me" class="inline-flex items-center">
            <input id="remember_me" type="checkbox" class="rounded border-gray-300 text-indigo-600 shadow-sm focus:ring-indigo-500" name="remember">
            <span class="ms-2 text-sm text-gray-600">{{ __('Remember me') }}</span>
        </label>

        <button type="submit" class="flex w-full justify-center items-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition ease-in-out duration-150">
            {{ __('Log in') }}
        </button>
    </form>

    <details class="mt-8 rounded-lg border border-gray-200 bg-gray-50 open:pb-3">
        <summary class="cursor-pointer select-none px-4 py-3 text-sm font-medium text-gray-700">
            Demo accounts
        </summary>
        <div class="px-4 pt-1 text-sm text-gray-600">
            <p class="text-xs text-gray-500 mb-2">Sign in with the email below — password for every account is <code class="rounded bg-gray-200 px-1 py-0.5">password</code>.</p>
            <ul class="space-y-1.5">
                <li class="flex items-center justify-between gap-2">
                    <code class="rounded bg-gray-200 px-1 py-0.5 truncate">demo@smsc.local</code>
                    <span class="shrink-0 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700">support</span>
                </li>
                <li class="flex items-center justify-between gap-2">
                    <code class="rounded bg-gray-200 px-1 py-0.5 truncate">admin@acme-retail.example</code>
                    <span class="shrink-0 rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700">user</span>
                </li>
                <li class="flex items-center justify-between gap-2">
                    <code class="rounded bg-gray-200 px-1 py-0.5 truncate">admin@northwind-logistics.example</code>
                    <span class="shrink-0 rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700">user</span>
                </li>
                <li class="flex items-center justify-between gap-2">
                    <code class="rounded bg-gray-200 px-1 py-0.5 truncate">admin@bluehorizon-travel.example</code>
                    <span class="shrink-0 rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700">user</span>
                </li>
            </ul>
        </div>
    </details>
</x-guest-layout>
