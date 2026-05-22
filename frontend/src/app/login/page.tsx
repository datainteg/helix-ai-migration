export default function LoginPage() {
  return (
    <div className="max-w-md mx-auto mt-16">
      <div className="rounded-xl border bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-helix-700 mb-6">Login</h1>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input type="email" className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="admin@example.com" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input type="password" className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="••••••••" />
          </div>
          <button className="w-full rounded-lg bg-helix-600 px-4 py-2 text-white font-medium hover:bg-helix-700">
            Sign In
          </button>
        </div>
        <p className="mt-4 text-xs text-gray-500 text-center">
          <a href="/setup/first-admin" className="text-helix-600 hover:underline">First admin setup</a>
        </p>
      </div>
    </div>
  );
}
