"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Search, User, Plus, ExternalLink, Edit, Phone, Mail, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { listCustomers } from "../api";
import { CustomerFormDialog } from "./customer-form-dialog";
import type { CustomerRead } from "../types";

export function CustomersTable() {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [customerDialogOpen, setCustomerDialogOpen] = React.useState(false);
  const [customerToEdit, setCustomerToEdit] = React.useState<CustomerRead | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["customers", "table", page, searchQuery],
    queryFn: () => listCustomers({ page, page_size: 20, q: searchQuery }),
  });

  const customers = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / 20));

  const handleEditCustomer = (customer: CustomerRead) => {
    setCustomerToEdit(customer);
    setCustomerDialogOpen(true);
  };

  const handleCreateCustomer = () => {
    setCustomerToEdit(null);
    setCustomerDialogOpen(true);
  };

  return (
    <div className="space-y-4">
      {/* Barra de Busca e Ação */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por nome ou código..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="pl-8 text-xs"
          />
        </div>

        <Button
          type="button"
          size="sm"
          onClick={handleCreateCustomer}
          className="text-xs gap-1.5 bg-primary"
        >
          <Plus className="h-4 w-4" />
          <span>Novo Assinante</span>
        </Button>
      </div>

      {/* Tabela de Assinantes */}
      <div className="rounded-lg border border-border overflow-hidden bg-card">
        <table className="w-full text-xs text-left" role="table" aria-label="Tabela de Clientes">
          <thead className="bg-muted/50 text-muted-foreground uppercase text-[10px] border-b border-border">
            <tr>
              <th className="p-3">Código</th>
              <th className="p-3">Nome / Razão Social</th>
              <th className="p-3">Contato</th>
              <th className="p-3">Endereço de Instalação</th>
              <th className="p-3">Versão ETag</th>
              <th className="p-3 text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-muted-foreground">
                  Carregando lista de assinantes...
                </td>
              </tr>
            ) : customers.length > 0 ? (
              customers.map((cust) => (
                <tr key={cust.id} className="hover:bg-muted/40 transition-colors">
                  <td className="p-3 font-mono font-bold text-foreground">
                    <Link
                      href={`/customers/${cust.id}`}
                      className="text-primary hover:underline"
                    >
                      {cust.code}
                    </Link>
                  </td>
                  <td className="p-3 font-medium text-foreground">
                    <div className="flex items-center gap-1.5">
                      <User className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>{cust.name}</span>
                    </div>
                  </td>
                  <td className="p-3 text-muted-foreground">
                    <div className="space-y-0.5">
                      {cust.phone && (
                        <div className="flex items-center gap-1">
                          <Phone className="h-3 w-3" />
                          <span>{cust.phone}</span>
                        </div>
                      )}
                      {cust.email && (
                        <div className="flex items-center gap-1">
                          <Mail className="h-3 w-3" />
                          <span>{cust.email}</span>
                        </div>
                      )}
                      {!cust.phone && !cust.email && <span>—</span>}
                    </div>
                  </td>
                  <td className="p-3 text-muted-foreground">
                    {cust.address ? (
                      <div className="flex items-center gap-1 truncate max-w-xs" title={cust.address}>
                        <MapPin className="h-3 w-3 shrink-0" />
                        <span className="truncate">{cust.address}</span>
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-3 font-mono text-[11px] text-muted-foreground">
                    v{cust.version}
                  </td>
                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditCustomer(cust)}
                        className="h-7 px-2 text-xs"
                        title="Editar cliente"
                      >
                        <Edit className="h-3.5 w-3.5" />
                      </Button>
                      <Link href={`/customers/${cust.id}`}>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs text-primary"
                          title="Ver ficha completa"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Button>
                      </Link>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="p-8 text-center text-muted-foreground">
                  Nenhum cliente cadastrado. Clique em &quot;Novo Assinante&quot; para começar.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Paginação */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Mostrando {customers.length} de {total} assinantes
          </span>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="h-7 text-xs"
            >
              Anterior
            </Button>
            <span className="px-2 font-mono">
              {page} / {totalPages}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className="h-7 text-xs"
            >
              Próxima
            </Button>
          </div>
        </div>
      )}

      {/* Modal de Criação / Edição */}
      <CustomerFormDialog
        open={customerDialogOpen}
        onOpenChange={setCustomerDialogOpen}
        customerToEdit={customerToEdit}
        onSuccess={() => {
          refetch();
        }}
      />
    </div>
  );
}
