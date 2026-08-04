"""Compatibility shim for older import paths used by Monday intake scripts."""

from intake_extractor.models.schema import ReferralIntake, RequestedService

__all__ = ["ReferralIntake", "RequestedService"]
