"use client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";
import type { Procedure } from "@/lib/api";

interface WorkflowDetailsModalProps {
  workflow: Procedure | null;
  open: boolean;
  onClose: () => void;
}

export function WorkflowDetailsModal({ workflow, open, onClose }: WorkflowDetailsModalProps) {
  if (!open || !workflow) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div className="relative w-full max-w-3xl bg-white rounded-xl border shadow-xl" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="flex items-start justify-between p-6 border-b">
            <div>
              <h2 className="text-xl font-semibold">{workflow.title}</h2>
              <p className="mt-1 text-sm text-gray-600">Xem trước quy trình làm việc và các bước</p>
            </div>
            <Button variant="outline" size="icon" className="bg-white" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6">
            {/* Mô tả */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Mô tả</div>
              <Card className="bg-white">
                <CardContent className="p-4">
                  <textarea
                    readOnly
                    value={workflow.description || ""}
                    rows={10}
                    className="w-full rounded-md border border-gray-300 p-2 text-sm text-gray-800 whitespace-pre-line"
                  />
                </CardContent>
              </Card>
            </div>

            {/* Lĩnh vực (placeholder) */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Lĩnh vực</div>
              <Input value="" placeholder="" readOnly className="bg-white" />
            </div>

            {/* Loại */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Loại</div>
              <div className="rounded-lg border p-4 text-sm text-gray-800">
                {workflow.type || "default"}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}