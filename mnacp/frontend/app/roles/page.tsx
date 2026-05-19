import RoleBuilder from "@/components/RoleBuilder";

export default function RolesPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <a href="/" className="text-indigo-400 hover:underline text-sm">← Ana sayfa</a>
        <h1 className="text-2xl font-bold">No-Code Rol Oluşturucu</h1>
        <p className="text-slate-400">
          Doğal dille yeni bir ajan rolü tanımla. Sistem uygun araçları otomatik önerir.
        </p>
        <RoleBuilder />
      </div>
    </main>
  );
}
