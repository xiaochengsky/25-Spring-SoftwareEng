from solders.pubkey import Pubkey
from construct import Struct, Int8ul, Int16ul, Int32ul, Bytes, PaddedString, Flag, GreedyBytes, If, Array, PrefixedArray, this
import base58
from construct import Struct, Int8ul, Int16ul, Int32ul, Bytes, PaddedString, Prefixed, Array
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *

METAPLEX_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")

CREATOR = Struct(
    "address" / Bytes(32),
    "verified" / Int8ul,
    "share" / Int8ul
)

# === Main Metadata Struct ===
METADATA_V1 = Struct(
    "key" / Int8ul,
    "update_authority" / Bytes(32),
    "mint" / Bytes(32),
    
    "name_len" / Int32ul,
    "name" / Bytes(this.name_len),

    "symbol_len" / Int32ul,
    "symbol" / Bytes(this.symbol_len),

    "uri_len" / Int32ul,
    "uri" / Bytes(this.uri_len),

    "seller_fee_basis_points" / Int16ul,
    
    "has_creators" / Flag,
    "creators" / If(this.has_creators, PrefixedArray(Int32ul, CREATOR)),

    "primary_sale_happened" / Flag,
    "is_mutable" / Flag,
    "edition_nonce" / Int8ul
)

def get_metadata_pda(mint: str):
    seed = [
        b"metadata",
        bytes(METAPLEX_PROGRAM_ID),
        bytes(Pubkey.from_string(mint)),
    ]
    metadata_pda, _ = Pubkey.find_program_address(seed, METAPLEX_PROGRAM_ID)

    return str(metadata_pda)

def parse_metaplex_data(data: bytes):
    parsed = METADATA_V1.parse(data)

    # === Format Output ===
    result = {
        "name": parsed.name.decode("utf-8").rstrip("\x00"),
        "symbol": parsed.symbol.decode("utf-8").rstrip("\x00"),
        "uri": parsed.uri.decode("utf-8").rstrip("\x00"),
        "seller_fee_basis_points": parsed.seller_fee_basis_points,
        "primary_sale_happened": parsed.primary_sale_happened,
        "mutable": parsed.is_mutable,
        "update_authority": base58.b58encode(parsed.update_authority).decode(),
        "mint": base58.b58encode(parsed.mint).decode(),
        "edition_nonce": parsed.edition_nonce,
        "creators": []
    }

    if parsed.has_creators:
        for creator in parsed.creators:
            result["creators"].append({
                "address": base58.b58encode(creator.address).decode(),
                "verified": creator.verified,
                "share": creator.share
            })
            
    return result