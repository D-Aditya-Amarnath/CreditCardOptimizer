from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INTERNAL_ERROR

from orchestrator import OfferAgentOrchestrator
from database import DatabaseManager

class A2AServer:
    """Agent-to-Agent Model Context Protocol Server."""
    
    def __init__(self):
        self.mcp = FastMCP("Financial Offer Agent OOP Server")
        self.orchestrator = OfferAgentOrchestrator()
        self.db = DatabaseManager()
        self._register_tools()
        
    def _register_tools(self):
        @self.mcp.tool()
        def get_best_financial_offer(merchant: str, amount: float) -> str:
            """
            Given a merchant and an intended purchase amount, this tool calculates and returns
            the best credit card to use based on the user's active promotional emails and offers.
            """
            try:
                offers = self.orchestrator.get_recommendation(merchant, amount)
                if not offers:
                    return f"No active promotional offers found for {merchant} on a purchase of {amount}."
                    
                best_offer, best_savings = offers[0]
                
                response = f"RECOMMENDED CARD: {best_offer.card_name}\n"
                response += f"Estimated Savings: {best_savings}\n"
                response += f"Offer Details: {best_offer.discount_percent}% {best_offer.offer_type}\n"
                if best_offer.max_cashback: response += f"Cap: Max {best_offer.max_cashback} limit\n"
                
                if len(offers) > 1:
                    response += "\nAlternatives:\n"
                    for off, sav in offers[1:3]:
                        response += f"- {off.card_name}: Saves {sav} ({off.discount_percent}% {off.offer_type})\n"
                        
                return response
            except Exception as e:
                raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))

        @self.mcp.tool()
        def list_active_offers_for_merchant(merchant: str) -> str:
            """
            Lists all active credit card promotional offers for a specific merchant without calculating exact checkout savings.
            """
            try:
                from datetime import datetime
                current_date = datetime.now()
                active_offers = self.db.get_all_active_offers_for_merchant(merchant)
                valid_offers = [o for o in active_offers if not (o.valid_until and o.valid_until < current_date)]
                     
                if not valid_offers:
                     return f"No active offers found in the database for {merchant}."
                     
                response = f"Found {len(valid_offers)} active offers for {merchant}:\n"
                for offer in valid_offers:
                     response += f"- '{offer.card_name}': {offer.discount_percent}% {offer.offer_type} "
                     if offer.min_spend: response += f"(Min Spend: {offer.min_spend}) "
                     if offer.max_cashback: response += f"(Max Cap: {offer.max_cashback}) "
                     if offer.valid_until: response += f"Expires: {offer.valid_until.date()}"
                     response += "\n"
                     
                return response
            except Exception as e:
                 raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))

    def run(self):
        print("Starting OOP A2A MCP Server...")
        self.mcp.run()

if __name__ == "__main__":
     server = A2AServer()
     server.run()
