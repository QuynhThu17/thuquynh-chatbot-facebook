"use client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { X, MessageSquare } from "lucide-react";
import type { Identity } from "@/lib/api";

interface IdentityDetailsModalProps {
  identity: Identity | null;
  open: boolean;
  onClose: () => void;
}

export function IdentityDetailsModal({ identity, open, onClose }: IdentityDetailsModalProps) {
  if (!open || !identity) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div className="relative w-full max-w-4xl bg-white rounded-xl border shadow-xl" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="flex items-start justify-between p-6 border-b">
            <div>
              <h2 className="text-xl font-semibold">{identity.title}</h2>
              <p className="mt-1 text-sm text-gray-600">Xem trước tính cách và phản hồi của danh tính này</p>
            </div>
            <Button variant="outline" size="icon" className="bg-white" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6">
            {/* Thông tin */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Thông tin</div>
              <Card className="bg-white">
                <CardContent className="p-4">
                  <textarea
                    readOnly
                    value={identity.description || ""}
                    rows={10}
                    className="w-full rounded-md border border-gray-300 p-2 text-sm text-gray-800 whitespace-pre-line"
                  />
                </CardContent>
              </Card>
            </div>

            {/* Phong cách */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Phong cách</div>
              <Input value="" placeholder="" readOnly className="bg-white" />
            </div>

            {/* Ví dụ hội thoại */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Ví dụ hội thoại</div>
              <div className="rounded-lg border p-4 text-sm text-gray-800">
                {identity.examples && identity.examples > 0 ? (
                  <div className="flex items-center text-gray-700">
                    <MessageSquare className="w-4 h-4 mr-2" />
                    Có {identity.examples} ví dụ hội thoại được định nghĩa.
                  </div>
                ) : (
                  <div>Chưa có ví dụ hội thoại.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}