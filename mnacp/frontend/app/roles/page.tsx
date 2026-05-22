import RoleBuilder from "@/components/RoleBuilder";

export default function RolesPage() {
  return (
    <main className="min-h-screen bg-slate-100 text-gray-900 p-8">
      <div className="max-w-2xl mx-auto space-y-6 animate-slide-up">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
          No-Code Rol Oluşturucu
        </h1>
        <p className="text-gray-500">
          Doğal dille yeni bir ajan rolü tanımla. Sistem uygun araçları otomatik önerir.
        </p>
        <RoleBuilder />
      </div>
    </main>
  );
}
