export default function FirstAdminSetupPage() {
  return (
    <div className="max-w-md mx-auto mt-16">
      <div className="rounded-xl border bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold text-helix-700 mb-6">First Admin Setup</h1>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input type="email" className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="admin@example.com" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input type="text" className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="Admin User" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input type="password" className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="••••••••" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Organization Name</label>
            <input type="text" className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="Acme Corp" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Organization Slug</label>
            <input type="text" className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm" placeholder="acme-corp" />
          </div>
          <button className="w-full rounded-lg bg-helix-600 px-4 py-2 text-white font-medium hover:bg-helix-700">
            Create Admin Account
          </button>
        </div>
      </div>
    </div>
  );
}
