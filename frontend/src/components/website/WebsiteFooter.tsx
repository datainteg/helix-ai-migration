import Link from "next/link";
import { Github } from "lucide-react";
import { HelixLogo } from "@/components/layout/HelixLogo";

export function WebsiteFooter() {
  return (
    <footer className="border-t border-hx-2 bg-app">
      <div className="max-w-[1200px] mx-auto px-8 py-12 grid grid-cols-2 md:grid-cols-5 gap-8 text-[13px] text-ink-3">
        <div className="col-span-2">
          <div className="inline-flex items-center gap-2.5 mb-3">
            <HelixLogo size={28} />
            <span className="font-semibold text-[15px] text-ink">Helix Migration</span>
          </div>
          <p className="max-w-xs leading-relaxed">
            Open-source, self-hosted, AI-powered migration and validation platform.
            <br />
            Apache 2.0 · Built for enterprise.
          </p>
        </div>
        <div>
          <h4 className="text-ink font-semibold text-[12px] uppercase tracking-wider mb-3">Product</h4>
          <ul className="space-y-2">
            <li><a href="#features" className="hover:text-ink">Features</a></li>
            <li><a href="#architecture" className="hover:text-ink">Architecture</a></li>
            <li><a href="#agents" className="hover:text-ink">Agent workflow</a></li>
            <li><a href="#open-source" className="hover:text-ink">Open source</a></li>
          </ul>
        </div>
        <div>
          <h4 className="text-ink font-semibold text-[12px] uppercase tracking-wider mb-3">Resources</h4>
          <ul className="space-y-2">
            <li><a href="https://github.com/datainteg/helix-ai-migration#readme" className="hover:text-ink">Documentation</a></li>
            <li><a href="https://github.com/datainteg/helix-ai-migration" className="hover:text-ink">GitHub</a></li>
            <li><Link href="/login" className="hover:text-ink">Sign in</Link></li>
            <li><Link href="/setup/first-admin" className="hover:text-ink">Self-host</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="text-ink font-semibold text-[12px] uppercase tracking-wider mb-3">Company</h4>
          <ul className="space-y-2">
            <li><a href="https://helix.datainteg.io" className="hover:text-ink">helix.datainteg.io</a></li>
            <li><a href="https://github.com/datainteg" className="hover:text-ink">datainteg.io</a></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-hx-2">
        <div className="max-w-[1200px] mx-auto px-8 h-14 flex items-center justify-between text-[12px] text-ink-4">
          <span>© 2026 Helix Migration · Apache 2.0</span>
          <a href="https://github.com/datainteg/helix-ai-migration" className="inline-flex items-center gap-1.5 hover:text-ink-2">
            <Github className="h-3.5 w-3.5" /> github.com/datainteg/helix-ai-migration
          </a>
        </div>
      </div>
    </footer>
  );
}
